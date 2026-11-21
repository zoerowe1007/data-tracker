import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from tracker import issues
from tracker.history import read_csv
from tracker.run import run
from tests.helpers import SOURCES, fake_http


def root_with_sources(tmp_path):
    shutil.copy(Path(__file__).parent.parent / "sources.json", tmp_path / "sources.json")
    return tmp_path


def at(day, hour=8):
    return datetime(2026, 11, day, hour, 17, 5, tzinfo=timezone.utc)


def go(root, now, **kw):
    return run(root, now=now, issue=False, pause=0, **kw)


def test_a_full_run_writes_raw_history_and_status(tmp_path):
    root = root_with_sources(tmp_path)
    results, status = go(root, at(16), http=fake_http())
    assert [r["ok"] for r in results] == [True, True, True]
    day = root / "data" / "raw" / "2026-11-16"
    assert sorted(p.name for p in day.iterdir()) == ["air.json.gz", "crypto.json.gz", "weather.json.gz"]
    assert len(read_csv(root / "data" / "history.csv")) == 12 + 12 + 12
    s = json.loads((root / "data" / "status.json").read_text())
    assert list(s) == ["run_time", "first_run_date", "days_with_success", "items", "new_today", "gone_today", "sources"]
    assert s["run_time"] == "2026-11-16T08:17:05Z" and s["first_run_date"] == "2026-11-16"
    assert s["days_with_success"] == 1 and s["items"] == 36 and s["new_today"] == 0 and s["gone_today"] == 0
    assert s["sources"] == [{"name": "crypto", "ok": True, "count": 12}, {"name": "weather", "ok": True, "count": 12},
                            {"name": "air", "ok": True, "count": 12}]


def test_one_failing_source_does_not_stop_the_run(tmp_path):
    root = root_with_sources(tmp_path)
    results, status = go(root, at(16), http=fake_http(fail=("crypto",)))
    assert [(r["name"], r["ok"]) for r in results] == [("crypto", False), ("weather", True), ("air", True)]
    assert "503" in results[0]["error"]
    day = root / "data" / "raw" / "2026-11-16"
    assert not (day / "crypto.json.gz").exists()  # a failed source writes no raw file
    assert {r["source"] for r in read_csv(root / "data" / "history.csv")} == {"air", "weather"}
    assert status["sources"][0] == {"name": "crypto", "ok": False, "count": 0}
    log = json.loads((root / "data" / "run_log.json").read_text())
    assert log["2026-11-16"][0]["ok"] is False and "error" in log["2026-11-16"][0]


def test_an_unreadable_response_counts_as_a_failure(tmp_path):
    root = root_with_sources(tmp_path)

    def http(url, **_):
        return b"<html>captcha</html>" if "air-quality" in url else fake_http()(url)
    results, _ = go(root, at(16), http=http)
    assert results[2]["ok"] is False and results[0]["ok"] and results[1]["ok"]
    assert not (root / "data" / "raw" / "2026-11-16" / "air.json.gz").exists()


def test_all_sources_failing_still_finishes(tmp_path):
    root = root_with_sources(tmp_path)
    results, status = go(root, at(16), http=fake_http(fail=("air", "crypto", "weather")))
    assert not any(r["ok"] for r in results)
    assert status["days_with_success"] == 0 and status["items"] == 0
    assert (root / "data" / "status.json").exists()


def test_a_second_run_on_the_same_day_replaces_that_day(tmp_path):
    root = root_with_sources(tmp_path)
    go(root, at(16, 8), http=fake_http(bump=0.0))
    go(root, at(17, 8), http=fake_http(bump=1.0))
    _, status = go(root, at(17, 20), http=fake_http(bump=5.0))  # same UTC day, new values
    rows = read_csv(root / "data" / "history.csv")
    on17 = [r for r in rows if r["date"] == "2026-11-17" and r["item_id"] == "air_austin"]
    assert len(on17) == 1 and on17[0]["us_aqi"] == 45.0  # replaced, not added
    assert len([r for r in rows if r["date"] == "2026-11-17"]) == 36
    assert status["days_with_success"] == 2 and status["run_time"] == "2026-11-17T20:17:05Z"


def test_a_failed_second_run_does_not_keep_the_old_file_for_that_source(tmp_path):
    root = root_with_sources(tmp_path)
    go(root, at(17, 8), http=fake_http())
    go(root, at(17, 20), http=fake_http(fail=("weather",)))
    assert not (root / "data" / "raw" / "2026-11-17" / "weather.json.gz").exists()
    log = json.loads((root / "data" / "run_log.json").read_text())
    assert len(log["2026-11-17"]) == 3 and log["2026-11-17"][1]["ok"] is False  # the day counts once


def test_new_and_gone_items_in_status(tmp_path):
    root = root_with_sources(tmp_path)
    go(root, at(16), http=fake_http(air={"missing": ("air_waco",)}))
    _, status = go(root, at(17), http=fake_http(air={"missing": ("air_austin",)}))
    assert status["new_today"] == 1 and status["gone_today"] == 1  # Waco appeared, Austin disappeared


def test_issue_is_titled_with_the_date_and_lists_old_and_new_values(tmp_path):
    root = root_with_sources(tmp_path)
    go(root, at(16), http=fake_http(bump=0.0, air={"missing": ("air_waco",)}))
    results, status = go(root, at(17), http=fake_http(bump=10.0, air={"missing": ("air_austin",)}))
    rows = read_csv(root / "data" / "history.csv")
    title, body = issues.build_issue("2026-11-17", rows, SOURCES, results, status, "https://x.github.io/y/")
    assert title == "2026-11-17"
    assert "3/3 sources ok" in body and "https://x.github.io/y/" in body
    assert "| Item | Source | Old | New | Change |" in body
    assert "## Appeared (1)" in body and "Waco, TX (air)" in body
    assert "## Disappeared (1)" in body and "Austin, TX (air)" in body
    first_move = body.split("|---|---|---:|---:|---:|")[1].splitlines()[1]
    assert "%" in first_move and "→" not in first_move
    assert body.count("\n| ") <= 1 + issues.MOVES_LISTED  # header row plus at most the top moves


def test_issue_on_a_day_with_no_changes(tmp_path):
    root = root_with_sources(tmp_path)
    go(root, at(16), http=fake_http())
    results, status = go(root, at(17), http=fake_http())
    title, body = issues.build_issue("2026-11-17", read_csv(root / "data" / "history.csv"), SOURCES, results, status)
    assert title == "2026-11-17" and "No changes since the previous run" in body


def test_issue_lists_a_failed_source(tmp_path):
    root = root_with_sources(tmp_path)
    results, status = go(root, at(16), http=fake_http(fail=("weather",)))
    _, body = issues.build_issue("2026-11-16", read_csv(root / "data" / "history.csv"), SOURCES, results, status)
    assert "## Sources that failed" in body and "`weather`" in body
    assert "No previous run to compare with yet" in body
