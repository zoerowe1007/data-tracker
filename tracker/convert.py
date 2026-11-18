"""Convert one raw file into rows with the common columns (no date: the date comes from the file's folder)."""
import csv
import io
import json
import math
from urllib.parse import quote

from .common import make_row

STOOQ_URL = "https://stooq.com/q/l/?s={symbols}&f=sd2t2ohlcv&h&e=csv"
COINGECKO_URL = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids={ids}"
                 "&order=market_cap_desc&per_page=250&page=1&sparkline=false&price_change_percentage=24h")
OPENMETEO_URL = ("https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}"
                 "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure"
                 "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=UTC")


class ConvertError(Exception):
    pass


def build_url(cfg):
    """The request for one source. Only the tracked items are asked for."""
    items = cfg["items"]
    kind = cfg["kind"]
    if kind == "stooq":
        return STOOQ_URL.format(symbols="+".join(i["symbol"] for i in items))
    if kind == "coingecko":
        return COINGECKO_URL.format(ids=quote(",".join(i["id"] for i in items), safe=","))
    if kind == "openmeteo":
        return OPENMETEO_URL.format(lats=",".join(str(i["lat"]) for i in items),
                                    lons=",".join(str(i["lon"]) for i in items))
    raise ConvertError(f"unknown source kind: {kind}")


def _stooq(raw, cfg):
    by_symbol = {i["symbol"].upper(): i for i in cfg["items"]}
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace")))
    rows, seen = [], set()
    for rec in reader:
        rec = {(k or "").strip().lower(): (v or "").strip() for k, v in rec.items()}
        item = by_symbol.get(rec.get("symbol", "").upper())
        if not item or item["id"] in seen:
            continue
        row = make_row(cfg, item, price=rec.get("close"), open=rec.get("open"), high=rec.get("high"),
                       low=rec.get("low"), volume=rec.get("volume"),
                       as_of=" ".join(x for x in (rec.get("date"), rec.get("time")) if x and x != "N/D"))
        if row["price"] == "":  # "N/D" means Stooq has no quote for the symbol
            continue
        seen.add(item["id"])
        rows.append(row)
    return rows


def _coingecko(raw, cfg):
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list):
        raise ConvertError("CoinGecko did not return a list")
    by_id = {i["id"]: i for i in cfg["items"]}
    rows, seen = [], set()
    for rec in data:
        item = by_id.get(rec.get("id"))
        if not item or item["id"] in seen:
            continue
        row = make_row(cfg, item, price=rec.get("current_price"), high=rec.get("high_24h"),
                       low=rec.get("low_24h"), volume=rec.get("total_volume"),
                       change_pct=rec.get("price_change_percentage_24h"),
                       market_cap=rec.get("market_cap"), as_of=rec.get("last_updated"))
        if row["price"] == "":
            continue
        seen.add(item["id"])
        rows.append(row)
    return rows


def _openmeteo(raw, cfg):
    data = json.loads(raw.decode("utf-8"))
    if isinstance(data, dict):
        if data.get("error"):
            raise ConvertError(f"Open-Meteo error: {data.get('reason')}")
        data = [data]
    rows, used = [], set()
    for loc in data:
        cur = loc.get("current") or {}
        if cur.get("temperature_2m") is None:
            continue
        # Open-Meteo snaps to its own grid, so match each answer to the nearest tracked city.
        best = min((i for i in cfg["items"] if i["id"] not in used),
                   key=lambda i: math.hypot(i["lat"] - loc.get("latitude", 1e9), i["lon"] - loc.get("longitude", 1e9)),
                   default=None)
        if best is None:
            continue
        used.add(best["id"])
        rows.append(make_row(cfg, best, temp_f=cur.get("temperature_2m"), humidity_pct=cur.get("relative_humidity_2m"),
                             wind_mph=cur.get("wind_speed_10m"), pressure_hpa=cur.get("surface_pressure"),
                             as_of=cur.get("time")))
    return rows


CONVERTERS = {"stooq": _stooq, "coingecko": _coingecko, "openmeteo": _openmeteo}


def convert(raw, cfg):
    """Rows for one source from the bytes it returned. Raises ConvertError if the bytes are unusable."""
    try:
        rows = CONVERTERS[cfg["kind"]](raw, cfg)
    except ConvertError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ConvertError(f"could not read the {cfg['name']} response: {exc}") from exc
    return rows
