"""Writes tests/fixtures/trends_history.csv (a small multi-day history with gaps) and
tests/fixtures/trends_expected.json (the Python reference numbers, the Today comparison and the Browse sorts).

    python tests/make_trends_fixture.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tracker.analysis import biggest_moves, compare  # noqa: E402
from tracker.common import load_sources  # noqa: E402
from tracker.history import read_csv  # noqa: E402
from tracker.run import run  # noqa: E402
from tracker.trends import compute  # noqa: E402
from tests.helpers import fake_http  # noqa: E402

BUMPS = [0, 1.5, -2, 3, 6, 2, -1]


def main():
    sources = load_sources()
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "sources.json").write_text((ROOT / "sources.json").read_text())
        for d, b in enumerate(BUMPS):
            kw, fail = {}, ()
            if d == 2:
                fail = ("crypto",)                       # a day on which one source failed
            if d == 4:
                kw = {"stocks": {"missing": ("TSN",)}}   # an item that disappears and comes back
            if d == 5:
                kw = {"stocks": {"missing": ("JPM",)}}   # JPM is then new on the last day
            if d == 6:
                kw = {"stocks": {"missing": ("WMT",)}}   # and WMT is gone on the last day
            run(tmp, now=datetime(2026, 11, 10 + d, 8, 17, 5, tzinfo=timezone.utc),
                http=fake_http(bump=b * (1 + d % 3), fail=fail, **kw), issue=False, pause=0)
        rows = read_csv(tmp / "data" / "history.csv")
        (ROOT / "tests" / "fixtures").mkdir(exist_ok=True)
        (ROOT / "tests" / "fixtures" / "trends_history.csv").write_text((tmp / "data" / "history.csv").read_text())
    diff = compare(rows, sources)
    expected = {
        "trends": compute(rows, sources),
        "today": {"latestDate": max(r["date"] for r in rows),
                  "moves": [{"item_id": m["item_id"], "pct": m["pct"], "old": m["old"], "new": m["new"]}
                            for m in biggest_moves(diff["changes"], 10)],
                  "new": [r["item_id"] for r in diff["new"]], "gone": [r["item_id"] for r in diff["gone"]]},
    }
    (ROOT / "tests" / "fixtures" / "trends_expected.json").write_text(json.dumps(expected, indent=1, sort_keys=True))
    print(f"{len(rows)} rows, {len(expected['trends']['days'])} days")


if __name__ == "__main__":
    main()
