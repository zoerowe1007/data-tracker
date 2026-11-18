import json

import pytest

from tracker.common import COLUMNS, NUMERIC
from tracker.convert import ConvertError, build_url, convert
from tests.helpers import BY_NAME, coingecko_bytes, openmeteo_bytes, stooq_bytes


def test_stocks_csv_to_common_columns():
    cfg = BY_NAME["stocks"]
    rows = convert(stooq_bytes(cfg), cfg)
    assert len(rows) == len(cfg["items"])  # the untracked symbol is dropped
    r = {x["item_id"]: x for x in rows}["WMT"]
    assert list(r) == COLUMNS
    assert (r["item"], r["source"], r["category"]) == ("Walmart", "stocks", "Retail")
    assert r["price"] == 50.0 and r["open"] == 49.0 and r["high"] == 52.0 and r["low"] == 48.0
    assert r["volume"] == 1000000.0
    assert r["as_of"] == "2026-11-16 22:00:09"
    assert r["temp_f"] == "" and r["market_cap"] == ""  # values this source does not report stay empty


def test_stocks_nd_symbol_has_no_row():
    cfg = BY_NAME["stocks"]
    rows = convert(stooq_bytes(cfg, nd=("TSN",)), cfg)
    assert "TSN" not in {r["item_id"] for r in rows}
    assert len(rows) == len(cfg["items"]) - 1


def test_crypto_json_to_common_columns():
    cfg = BY_NAME["crypto"]
    rows = convert(coingecko_bytes(cfg), cfg)
    assert len(rows) == len(cfg["items"])
    r = {x["item_id"]: x for x in rows}["bitcoin"]
    assert (r["item"], r["source"], r["category"]) == ("Bitcoin", "crypto", "Crypto")
    assert r["price"] == 100.0 and r["change_pct"] == 1.5 and r["market_cap"] == 100.0 * 1e6
    assert r["high"] == 105.0 and r["low"] == 95.0 and r["volume"] == 100000.0
    assert r["as_of"] == "2026-11-17T20:30:00.000Z"


def test_weather_json_matches_each_city_by_nearest_location():
    cfg = BY_NAME["weather"]
    rows = convert(openmeteo_bytes(cfg), cfg)
    got = {r["item_id"]: r for r in rows}
    assert set(got) == {i["id"] for i in cfg["items"]}
    assert got["dallas"]["temp_f"] == 60.0 and got["dallas"]["humidity_pct"] == 40.0
    assert got["fortworth"]["temp_f"] == 61.0 and got["fortworth"]["pressure_hpa"] == 991.0
    assert got["dallas"]["wind_mph"] == 5.0


def test_a_single_weather_answer_is_still_read():
    cfg = {**BY_NAME["weather"], "items": BY_NAME["weather"]["items"][:1]}
    one = json.loads(openmeteo_bytes(cfg))[0]
    rows = convert(json.dumps(one).encode(), cfg)
    assert len(rows) == 1 and rows[0]["item_id"] == "dallas"


def test_every_numeric_column_is_a_float_or_empty():
    for cfg in BY_NAME.values():
        fn = {"stocks": stooq_bytes, "crypto": coingecko_bytes, "weather": openmeteo_bytes}[cfg["name"]]
        for r in convert(fn(cfg), cfg):
            assert all(r[c] == "" or isinstance(r[c], float) for c in NUMERIC)
            assert sum(r[c] != "" for c in NUMERIC) >= 2  # at least two numeric values per item


@pytest.mark.parametrize("name,junk", [("stocks", b"<html>blocked</html>"), ("crypto", b"{not json"),
                                       ("weather", b'{"error": true, "reason": "limit"}'),
                                       ("crypto", b'{"status": {"error_code": 429}}')])
def test_unreadable_responses_raise_or_give_no_rows(name, junk):
    cfg = BY_NAME[name]
    try:
        rows = convert(junk, cfg)
    except ConvertError:
        return
    assert rows == []


def test_requests_ask_only_for_the_tracked_items():
    url = build_url(BY_NAME["crypto"])
    assert "ids=bitcoin,ethereum" in url and "vs_currency=usd" in url
    assert build_url(BY_NAME["stocks"]).count(".us") == len(BY_NAME["stocks"]["items"])
    assert "latitude=32.7767," in build_url(BY_NAME["weather"])
    assert "fahrenheit" in build_url(BY_NAME["weather"])
