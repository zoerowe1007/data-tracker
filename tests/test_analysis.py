import pytest

from tracker.analysis import biggest_moves, compare, move_pct
from tracker.common import COLUMNS

SRC = [{"name": "air", "headline": "price"}, {"name": "weather", "headline": "temp_f"}]


def row(date, item_id, source="air", **v):
    r = {c: "" for c in COLUMNS}
    r.update(date=date, item_id=item_id, item=item_id.title(), source=source)
    r.update(v)
    return r


def test_move_is_percent_change():
    assert move_pct(100.0, 110.0, "price") == pytest.approx(10.0)
    assert move_pct(200.0, 150.0, "price") == pytest.approx(-25.0)
    assert move_pct(50.0, 50.0, "price") == 0.0


def test_move_of_a_missing_value_is_none():
    assert move_pct("", 5.0, "price") is None
    assert move_pct(5.0, "", "price") is None


def test_temperature_move_never_divides_by_less_than_20():
    assert move_pct(2.0, 4.0, "temp_f") == pytest.approx(10.0)      # 2 / 20
    assert move_pct(-10.0, 10.0, "temp_f") == pytest.approx(100.0)  # 20 / 20
    assert move_pct(50.0, 55.0, "temp_f") == pytest.approx(10.0)


def test_compare_old_and_new_values_and_biggest_moves():
    rows = [row("2026-11-16", "a", price=100.0), row("2026-11-16", "b", price=10.0),
            row("2026-11-17", "a", price=101.0), row("2026-11-17", "b", price=12.0)]
    diff = compare(rows, SRC)
    by = {c["item_id"]: c for c in diff["changes"]}
    assert by["a"]["old"] == 100.0 and by["a"]["new"] == 101.0 and by["a"]["pct"] == pytest.approx(1.0)
    assert by["b"]["pct"] == pytest.approx(20.0)
    assert [m["item_id"] for m in biggest_moves(diff["changes"])] == ["b", "a"]
    assert diff["new"] == [] and diff["gone"] == []


def test_items_that_appear_or_disappear():
    rows = [row("2026-11-16", "a", price=1.0), row("2026-11-16", "gone", price=1.0),
            row("2026-11-17", "a", price=1.0), row("2026-11-17", "fresh", price=1.0)]
    diff = compare(rows, SRC)
    assert [r["item_id"] for r in diff["new"]] == ["fresh"]
    assert [r["item_id"] for r in diff["gone"]] == ["gone"]
    fresh = [c for c in diff["changes"] if c["item_id"] == "fresh"][0]
    assert fresh["is_new"] and fresh["pct"] is None


def test_first_run_has_nothing_to_compare():
    diff = compare([row("2026-11-17", "a", price=1.0)], SRC)
    assert diff["new"] == [] and diff["gone"] == []
    assert diff["changes"][0]["pct"] is None


def test_a_source_that_failed_today_is_not_compared():
    rows = [row("2026-11-16", "a", price=1.0), row("2026-11-16", "x", "weather", temp_f=50.0),
            row("2026-11-17", "x", "weather", temp_f=55.0)]  # air has no raw file on the 17th
    diff = compare(rows, SRC)
    assert diff["gone"] == [] and {c["source"] for c in diff["changes"]} == {"weather"}
    assert diff["latest"] == {"air": "2026-11-16", "weather": "2026-11-17"}


def test_comparison_skips_days_a_source_has_no_file():
    rows = [row("2026-11-14", "a", price=100.0), row("2026-11-17", "a", price=110.0),
            row("2026-11-16", "z", "weather", temp_f=1.0), row("2026-11-17", "z", "weather", temp_f=1.0)]
    by = {c["item_id"]: c for c in compare(rows, SRC)["changes"]}
    assert by["a"]["old"] == 100.0  # the previous run for air is the 14th, not the 16th
