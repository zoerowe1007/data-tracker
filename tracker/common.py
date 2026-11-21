"""Column definitions shared by the converters, the history build and the site."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The first four columns are fixed by the assignment; the rest are ours.
COLUMNS = ["date", "item_id", "item", "source", "category",
           "price", "high", "low", "volume", "change_pct", "market_cap",
           "temp_f", "humidity_pct", "wind_mph", "pressure_hpa",
           "us_aqi", "pm2_5", "pm10", "ozone", "as_of"]
NUMERIC = ["price", "high", "low", "volume", "change_pct", "market_cap",
           "temp_f", "humidity_pct", "wind_mph", "pressure_hpa",
           "us_aqi", "pm2_5", "pm10", "ozone"]
TEXT = [c for c in COLUMNS if c not in NUMERIC]


def load_sources(path=None):
    path = Path(path) if path else ROOT / "sources.json"
    return json.loads(path.read_text(encoding="utf-8"))["sources"]


def number(value):
    """A float, or '' when the source gave nothing usable."""
    if value is None or isinstance(value, bool):
        return ""
    try:
        x = float(value)
    except (TypeError, ValueError):
        return ""
    return x if x == x and x not in (float("inf"), float("-inf")) else ""


def make_row(cfg, item, **values):
    """One converted row with every column present (missing values are '')."""
    row = {c: "" for c in COLUMNS}
    row.update(item_id=item["id"], item=item["item"], source=cfg["name"], category=item.get("category", ""))
    for key, val in values.items():
        row[key] = number(val) if key in NUMERIC else ("" if val is None else str(val).strip())
    return row
