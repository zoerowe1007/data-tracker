"""Fake downloads that look like the three real sources, for tests that run offline."""
import json

from tracker.common import load_sources
from tracker.http import HttpError

SOURCES = load_sources()
BY_NAME = {s["name"]: s for s in SOURCES}


def stooq_bytes(cfg, bump=0.0, missing=(), nd=()):
    lines = ["Symbol,Date,Time,Open,High,Low,Close,Volume"]
    for n, it in enumerate(cfg["items"]):
        sym = it["symbol"].upper()
        if it["id"] in missing:
            continue
        if it["id"] in nd:
            lines.append(f"{sym},N/D,N/D,N/D,N/D,N/D,N/D,N/D")
            continue
        base = 50 + n * 10 + bump
        lines.append(f"{sym},2026-11-16,22:00:09,{base - 1},{base + 2},{base - 2},{base},{1000000 + n}")
    lines.append("UNTRACKED.US,2026-11-16,22:00:09,1,2,0.5,1.5,10")  # a symbol we did not ask for
    return ("\n".join(lines) + "\n").encode()


def coingecko_bytes(cfg, bump=0.0, missing=()):
    out = []
    for n, it in enumerate(cfg["items"]):
        if it["id"] in missing:
            continue
        price = 100.0 * (n + 1) + bump
        out.append({"id": it["id"], "symbol": it["id"][:3], "name": it["item"], "current_price": price,
                    "market_cap": price * 1e6, "total_volume": price * 1e3, "high_24h": price + 5,
                    "low_24h": price - 5, "price_change_percentage_24h": 1.5 + n / 10,
                    "last_updated": "2026-11-17T20:30:00.000Z"})
    out.append({"id": "not-tracked", "current_price": 1})
    return json.dumps(out).encode()


def openmeteo_bytes(cfg, bump=0.0, skip=()):
    out = []
    for n, it in enumerate(cfg["items"]):
        if it["id"] in skip:
            continue
        out.append({"latitude": round(it["lat"] + 0.02, 2), "longitude": round(it["lon"] - 0.03, 2),  # snapped grid
                    "current": {"time": "2026-11-17T20:15", "temperature_2m": 60.0 + n + bump,
                                "relative_humidity_2m": 40 + n, "wind_speed_10m": 5 + n / 2,
                                "surface_pressure": 990.0 + n}})
    return json.dumps(out).encode()


def fake_http(bump=0.0, fail=(), **kw):
    """A stand-in for tracker.http.fetch_bytes. Sources named in `fail` raise like a dead download."""
    def http(url, **_):
        for name, cfg in BY_NAME.items():
            marker = {"stocks": "stooq.com", "crypto": "coingecko.com", "weather": "open-meteo.com"}[name]
            if marker in url:
                if name in fail:
                    raise HttpError(f"HTTP 503 from {marker}")
                if name == "stocks":
                    return stooq_bytes(cfg, bump, **kw.get("stocks", {}))
                if name == "crypto":
                    return coingecko_bytes(cfg, bump, **kw.get("crypto", {}))
                return openmeteo_bytes(cfg, bump, **kw.get("weather", {}))
        raise AssertionError(f"unexpected url {url}")
    return http
