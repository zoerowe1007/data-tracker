"""data/status.json: a description of the latest run."""
import json
from pathlib import Path

from .analysis import compare
from .rawstore import list_days


def build_status(rows, results, now, raw_dir, sources):
    """Status for the run at `now` (a UTC datetime).

    rows     history rows after the build
    results  [{name, ok, count[, error]}], one per source, from this run
    """
    days = list_days(raw_dir)
    today = now.strftime("%Y-%m-%d")
    diff = compare(rows, sources)
    return {
        "run_time": now.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_run_date": min(days) if days else "",
        "days_with_success": len(days),
        "items": sum(1 for r in rows if r["date"] == today),
        "new_today": len(diff["new"]),
        "gone_today": len(diff["gone"]),
        "sources": [{"name": s["name"], "ok": bool(s["ok"]), "count": int(s["count"])} for s in results],
    }


def write_status(status, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def update_run_log(path, date, results):
    """Keep every day's per-source outcome, including the reason for a failure (a failed source leaves no
    raw file). A second run on the same day replaces that day's entry."""
    path = Path(path)
    log = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    log[date] = results
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(log.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
