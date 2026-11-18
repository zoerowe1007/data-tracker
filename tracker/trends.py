"""Python reference for the Trends page: the same numbers, computed from history.csv rows.

assets/trends-calc.js computes them in the browser; tests/market_check.mjs-style cross-check
(tests/trends_check.mjs) compares the two on a fixture history.
"""
import math
import statistics

from .analysis import move_pct


def _mean(xs):
    return sum(xs) / len(xs)


def compute(rows, sources):
    headline = {s["name"]: s.get("headline", "price") for s in sources}
    items, dates = {}, set()
    for r in rows:
        dates.add(r["date"])
        col = headline[r["source"]]
        v = r[col]
        if v == "":
            continue
        it = items.setdefault(r["item_id"], {"item_id": r["item_id"], "item": r["item"], "source": r["source"],
                                              "column": col, "points": []})
        it["points"].append((r["date"], v))
    ids = sorted(items)
    for i in ids:
        items[i]["points"].sort()

    since_first = []
    for i in ids:
        it, p = items[i], items[i]["points"]
        if len(p) < 2:
            continue
        since_first.append({"item_id": i, "item": it["item"], "source": it["source"], "first": p[0][1], "last": p[-1][1],
                            "pct": move_pct(p[0][1], p[-1][1], it["column"])})
    since_first.sort(key=lambda s: (-s["pct"], s["item_id"]))
    riser = since_first[0] if since_first else None
    faller = min(since_first, key=lambda s: (s["pct"], s["item_id"])) if since_first else None

    moves, per_item = [], {}
    for i in ids:
        it, p = items[i], items[i]["points"]
        for k in range(1, len(p)):
            m = {"date": p[k][0], "item_id": i, "item": it["item"], "pct": move_pct(p[k - 1][1], p[k][1], it["column"])}
            moves.append(m)
            per_item.setdefault(i, []).append(m["pct"])
    by_date = {}
    for m in moves:
        by_date.setdefault(m["date"], []).append(m)
    daily = []
    for d in sorted(by_date):
        ms = sorted(by_date[d], key=lambda m: (-abs(m["pct"]), m["item_id"]))
        daily.append({"date": d, "n": len(ms), "maxItemId": ms[0]["item_id"], "maxPct": ms[0]["pct"],
                      "maxAbs": abs(ms[0]["pct"]), "meanAbs": _mean([abs(m["pct"]) for m in ms])})
    biggest = min(moves, key=lambda m: (-abs(m["pct"]), m["item_id"], m["date"])) if moves else None

    temps = {}
    for r in rows:
        if r["temp_f"] != "":
            temps.setdefault(r["date"], []).append(r)
    daily_gap, spread = [], None
    for d in sorted(temps):
        cs = temps[d]
        if len(cs) >= 2:
            daily_gap.append({"date": d, "gap": max(c["temp_f"] for c in cs) - min(c["temp_f"] for c in cs), "n": len(cs)})
    if temps:
        d = max(temps)
        desc = sorted(temps[d], key=lambda r: (-r["temp_f"], r["item_id"]))
        asc = sorted(temps[d], key=lambda r: (r["temp_f"], r["item_id"]))
        spread = {"date": d, "n": len(desc), "hottest": {"item": desc[0]["item"], "temp": desc[0]["temp_f"]},
                  "coldest": {"item": asc[0]["item"], "temp": asc[0]["temp_f"]},
                  "gap": desc[0]["temp_f"] - asc[0]["temp_f"],
                  "cities": [{"item": r["item"], "temp": r["temp_f"]} for r in desc]}

    groups = {}
    for s in since_first:
        groups.setdefault(s["source"], []).append(s["pct"])
    by_source = sorted(({"source": k, "mean": _mean(v), "n": len(v)} for k, v in groups.items()),
                       key=lambda g: (-g["mean"], g["source"]))

    volatility = sorted(({"item_id": i, "item": items[i]["item"], "source": items[i]["source"],
                          "sd": statistics.stdev(v), "n": len(v)} for i, v in per_item.items() if len(v) >= 2),
                        key=lambda g: (-g["sd"], g["item_id"]))
    return {"days": sorted(dates), "items": len(ids), "sinceFirst": since_first, "riser": riser, "faller": faller,
            "daily": daily, "biggest": biggest, "spread": spread, "dailyGap": daily_gap, "bySource": by_source,
            "volatility": volatility}


__all__ = ["compute", "math"]
