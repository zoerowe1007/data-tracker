"""The move rule and the per-run comparison (the site repeats this in JavaScript)."""
from .common import NUMERIC

DENOMINATOR_FLOOR = 20.0  # keeps a reading near zero (a cold morning in °F) from giving a huge percent


def move_pct(old, new, headline):
    """Percent change of an item's headline value since the previous run.

    (new - old) / |old| * 100. For temperatures the denominator is never smaller than 20,
    so a change from 2°F to 4°F is 10%, not 100%.
    """
    if old == "" or new == "" or old is None or new is None:
        return None
    floor = DENOMINATOR_FLOOR if headline == "temp_f" else 1e-12
    base = max(abs(old), floor)
    return (new - old) / base * 100.0


def compare(rows, sources):
    """Compare each source's latest run with the run before it.

    Returns {"changes": [...], "new": [...], "gone": [...], "latest": {source: date}}.
    A run is a day on which the source has a raw file. A source that is missing from the
    latest overall day (it failed) is not compared, so its items are neither new nor gone.
    """
    headline = {s["name"]: s.get("headline", "price") for s in sources}
    by_source = {}
    for r in rows:
        by_source.setdefault(r["source"], {}).setdefault(r["date"], {})[r["item_id"]] = r
    latest_all = max((r["date"] for r in rows), default="")
    changes, new, gone, latest = [], [], [], {}
    for name, days in by_source.items():
        dates = sorted(days)
        last = dates[-1]
        latest[name] = last
        if last != latest_all:
            continue
        prev = days[dates[-2]] if len(dates) > 1 else None
        for item_id, row in sorted(days[last].items()):
            old_row = prev.get(item_id) if prev else None
            col = headline[name]
            entry = {"item_id": item_id, "item": row["item"], "source": name, "column": col,
                     "new": row[col], "old": old_row[col] if old_row else "",
                     "pct": move_pct(old_row[col], row[col], col) if old_row else None,
                     "is_new": bool(prev) and old_row is None}
            changes.append(entry)
            if entry["is_new"]:
                new.append(row)
        if prev:
            gone.extend(r for i, r in sorted(prev.items()) if i not in days[last])
    return {"changes": changes, "new": new, "gone": gone, "latest": latest}


def biggest_moves(changes, limit=10):
    movers = [c for c in changes if c["pct"] is not None]
    movers.sort(key=lambda c: (-abs(c["pct"]), c["item_id"]))
    return movers[:limit]


__all__ = ["compare", "biggest_moves", "move_pct", "NUMERIC"]
