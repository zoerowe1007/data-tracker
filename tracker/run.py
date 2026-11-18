"""The daily pipeline:  python -m tracker.run

1. call every source and save what it returned (raw files)
2. build data/history.csv from the raw files
3. write data/status.json
4. open the day's GitHub Issue and close the previous one
(the workflow then commits the files)
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import issues
from .common import ROOT, load_sources
from .convert import ConvertError, build_url, convert
from .history import build_history
from .http import fetch_bytes
from .rawstore import clear_day, write_raw
from .status import build_status, update_run_log, write_status


def run_sources(sources, raw_dir, date, http=fetch_bytes, pause=1.5):
    """Call every source. A failing source writes no raw file and does not stop the others."""
    results = []
    for i, cfg in enumerate(sources):
        if i and pause:
            time.sleep(pause)
        try:
            payload = http(build_url(cfg))
            rows = convert(payload, cfg)  # a response we cannot read is a failure, not a raw file
            if not rows:
                raise ConvertError("the response held none of the tracked items")
            write_raw(raw_dir, date, cfg["name"], cfg["format"], payload)
            results.append({"name": cfg["name"], "ok": True, "count": len(rows)})
        except Exception as exc:  # noqa: BLE001  (any failure is recorded; the run goes on)
            results.append({"name": cfg["name"], "ok": False, "count": 0, "error": str(exc)[:300]})
    return results


def run(root=ROOT, now=None, http=fetch_bytes, issue=True, pause=1.5):
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    date = now.strftime("%Y-%m-%d")
    sources = load_sources(root / "sources.json")
    raw_dir = root / "data" / "raw"
    clear_day(raw_dir, date)  # a second run on the same UTC day replaces that day
    results = run_sources(sources, raw_dir, date, http=http, pause=pause)
    update_run_log(root / "data" / "run_log.json", date, results)
    rows = build_history(root)
    status = build_status(rows, results, now, raw_dir, sources)
    write_status(status, root / "data" / "status.json")
    if issue:
        try:
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            site = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/" if "/" in repo else ""
            title, body = issues.build_issue(date, rows, sources, results, status, site)
            print(f"Issue #{issues.publish(title, body)} updated: {title}")
        except Exception as exc:  # noqa: BLE001  (the data is what matters; the Issue is a report)
            print(f"::warning::could not publish the Issue: {exc}")
    return results, status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-issue", action="store_true", help="skip the GitHub Issue")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    results, status = run(args.root, issue=not args.no_issue)
    for s in results:
        print(f"{'ok  ' if s['ok'] else 'FAIL'} {s['name']:10} {s['count']:3} items" + ("" if s["ok"] else f"  {s['error']}"))
    print(f"days with a raw file: {status['days_with_success']} · items today: {status['items']}")
    return 0 if any(s["ok"] for s in results) else 1


if __name__ == "__main__":
    sys.exit(main())
