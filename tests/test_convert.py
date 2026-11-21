import json

import pytest

from tracker.common import COLUMNS, NUMERIC
from tracker.convert import ConvertError, build_url, convert
from tests.helpers import BY_NAME, air_bytes, coingecko_bytes, openmeteo_bytes


def test_air_json_to_common_columns():
    cfg = BY_NAME["air"]
    rows = convert(air_bytes(cfg), cfg)
    assert len(rows) == len(cfg["items"])
    r = {x["item_id"]: x for x in rows}["air_austin"]
    assert list(r) == COLUMNS
    assert (r["item"], r["source"], r["category"]) == ("Austin, TX", "air", "Texas")
    assert r["us_aqi"] == 40.0 and r["pm2_5"] == 8.0 and r["pm10"] == 15.0 and r["ozone"] == 60.0
    assert r["as_of"] == "2026-11-17T20:00"
    assert r["temp_f"] == "" and r["market_cap"] == ""  # values this source does not report stay empty


def test_air_answers_are_matched_to_cities_by_nearest_location():
    cfg = BY_NAME["air"]
    got = {r["item_id"]: r for r in convert(air_bytes(cfg), cfg)}
    assert got["air_sanantonio"]["us_aqi"] == 45.0 and got["air_sanantonio"]["pm2_5"] == 9.0


def test_an_air_place_without_a_reading_has_no_row():
    cfg = BY_NAME["air"]
    rows = convert(air_bytes(cfg, missing=("air_waco",)), cfg)
    assert "air_waco" not in {r["item_id"] for r in rows} and len(rows) == len(cfg["items"]) - 1
    data = json.loads(air_bytes(cfg))
    data[0]["current"]["us_aqi"] = None
    assert len(convert(json.dumps(data).encode(), cfg)) == len(cfg["items"]) - 1


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
        fn = {"air": air_bytes, "crypto": coingecko_bytes, "weather": openmeteo_bytes}[cfg["name"]]
        for r in convert(fn(cfg), cfg):
            assert all(r[c] == "" or isinstance(r[c], float) for c in NUMERIC)
            assert sum(r[c] != "" for c in NUMERIC) >= 2  # at least two numeric values per item


@pytest.mark.parametrize("name,junk", [("air", b"<html>blocked</html>"), ("air", b'{"error": true, "reason": "limit"}'), ("crypto", b"{not json"),
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
    air = build_url(BY_NAME["air"])
    assert air.startswith("https://air-quality-api.open-meteo.com/") and "current=us_aqi,pm2_5,pm10,ozone" in air
    assert len(air.split("latitude=")[1].split("&")[0].split(",")) == len(BY_NAME["air"]["items"])
    assert "latitude=32.7767," in build_url(BY_NAME["weather"])
    assert "fahrenheit" in build_url(BY_NAME["weather"])
