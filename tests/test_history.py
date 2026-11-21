import csv
import json
import shutil
from pathlib import Path

from tracker.common import COLUMNS, load_sources
from tracker.history import build_history, build_rows, read_csv
from tracker.rawstore import list_days, raw_path, read_raw, write_raw
from tests.helpers import BY_NAME, SOURCES, air_bytes, coingecko_bytes


def setup_root(tmp_path):
    shutil.copy(Path(__file__).parent.parent / "sources.json", tmp_path / "sources.json")
    return tmp_path


def put(root, date, name, payload):
    cfg = BY_NAME[name]
    return write_raw(root / "data" / "raw", date, name, cfg["format"], payload)


def test_raw_files_are_stored_as_received_and_compressed(tmp_path):
    payload = air_bytes(BY_NAME["air"])
    path = put(tmp_path, "2026-11-16", "air", payload)
    assert path == raw_path(tmp_path / "data" / "raw", "2026-11-16", "air", "json")
    assert path.name == "air.json.gz" and read_raw(path) == payload


def test_history_has_fixed_columns_and_is_sorted_by_date_then_item_id(tmp_path):
    root = setup_root(tmp_path)
    for d, bump in (("2026-11-17", 1.0), ("2026-11-16", 0.0)):  # written out of order on purpose
        put(root, d, "air", air_bytes(BY_NAME["air"], bump))
        put(root, d, "crypto", coingecko_bytes(BY_NAME["crypto"], bump))
    rows = build_history(root)
    keys = [(r["date"], r["item_id"]) for r in rows]
    assert keys == sorted(keys)
    with open(root / "data" / "history.csv", newline="") as fh:
        lines = list(csv.reader(fh))
    assert lines[0] == COLUMNS and lines[0][:4] == ["date", "item_id", "item", "source"]
    assert len(lines) - 1 == 2 * (12 + 12)
    assert len({(r["date"], r["item_id"]) for r in rows}) == len(rows)  # one row per item per day


def test_values_a_source_does_not_report_are_empty(tmp_path):
    root = setup_root(tmp_path)
    put(root, "2026-11-16", "air", air_bytes(BY_NAME["air"]))
    build_history(root)
    austin = [r for r in read_csv(root / "data" / "history.csv") if r["item_id"] == "air_austin"][0]
    assert austin["us_aqi"] == 40.0 and austin["temp_f"] == "" and austin["market_cap"] == "" and austin["price"] == ""


def test_building_twice_gives_the_same_file(tmp_path):
    root = setup_root(tmp_path)
    put(root, "2026-11-16", "air", air_bytes(BY_NAME["air"]))
    put(root, "2026-11-17", "crypto", coingecko_bytes(BY_NAME["crypto"]))
    build_history(root)
    first = (root / "data" / "history.csv").read_bytes()
    (root / "data" / "history.csv").unlink()
    build_history(root)
    assert (root / "data" / "history.csv").read_bytes() == first


def test_history_depends_on_the_raw_files_alone(tmp_path):
    root = setup_root(tmp_path)
    put(root, "2026-11-16", "air", air_bytes(BY_NAME["air"]))
    (root / "data").mkdir(exist_ok=True)
    (root / "data" / "history.csv").write_text("garbage\n")
    (root / "data" / "status.json").write_text("{}")
    build_history(root)
    assert "garbage" not in (root / "data" / "history.csv").read_text()


def test_a_day_without_a_raw_file_for_a_source_has_no_rows_from_it(tmp_path):
    root = setup_root(tmp_path)
    put(root, "2026-11-16", "air", air_bytes(BY_NAME["air"]))
    put(root, "2026-11-16", "crypto", coingecko_bytes(BY_NAME["crypto"]))
    put(root, "2026-11-17", "air", air_bytes(BY_NAME["air"]))  # crypto failed on the 17th
    rows = build_rows(root / "data" / "raw", SOURCES)
    assert {r["source"] for r in rows if r["date"] == "2026-11-17"} == {"air"}
    assert {r["source"] for r in rows if r["date"] == "2026-11-16"} == {"air", "crypto"}


def test_a_change_to_a_rule_applies_to_every_day(tmp_path):
    root = setup_root(tmp_path)
    for d in ("2026-11-16", "2026-11-17"):
        put(root, d, "air", air_bytes(BY_NAME["air"]))
    before = build_history(root)
    assert {r["item"] for r in before if r["item_id"] == "air_austin"} == {"Austin, TX"}
    cfg = json.loads((root / "sources.json").read_text())
    air = [x for x in cfg["sources"] if x["name"] == "air"][0]
    air["items"][0]["item"] = "Austin, Texas"  # a rule that lives in sources.json
    (root / "sources.json").write_text(json.dumps(cfg))
    after = build_history(root)
    assert {r["item"] for r in after if r["item_id"] == "air_austin"} == {"Austin, Texas"}  # old days follow it too


def test_a_source_removed_from_the_config_is_ignored(tmp_path):
    root = setup_root(tmp_path)
    put(root, "2026-11-16", "air", air_bytes(BY_NAME["air"]))
    put(root, "2026-11-16", "crypto", coingecko_bytes(BY_NAME["crypto"]))
    cfg = json.loads((root / "sources.json").read_text())
    cfg["sources"] = [s for s in cfg["sources"] if s["name"] != "crypto"]
    (root / "sources.json").write_text(json.dumps(cfg))
    assert {r["source"] for r in build_history(root)} == {"air"}


def test_list_days_finds_every_raw_file(tmp_path):
    put(tmp_path, "2026-11-17", "crypto", b"[]")
    put(tmp_path, "2026-11-16", "air", b"x")
    (tmp_path / "data" / "raw" / "notes").mkdir()
    days = list_days(tmp_path / "data" / "raw")
    assert list(days) == ["2026-11-16", "2026-11-17"] and set(days["2026-11-17"]) == {"crypto"}
