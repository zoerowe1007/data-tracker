"""Build data/history.csv from the raw files alone.

    python -m tracker.history          # rebuilds data/history.csv from data/raw/
"""
import csv
import sys
from pathlib import Path

from .common import COLUMNS, NUMERIC, ROOT, load_sources
from .convert import convert
from .rawstore import list_days, read_raw


def build_rows(raw_dir, sources):
    """Day by day: convert every raw file to the common columns. A source with no raw file that day adds no rows."""
    cfgs = {s["name"]: s for s in sources}
    rows = []
    for date, files in list_days(raw_dir).items():
        for name, path in files.items():
            cfg = cfgs.get(name)
            if cfg is None:  # a source that was removed from sources.json
                continue
            for row in convert(read_raw(path), cfg):
                row["date"] = date
                rows.append(row)
    rows.sort(key=lambda r: (r["date"], r["item_id"]))
    return rows


def _cell(value):
    if value == "":
        return ""
    if isinstance(value, float):
        return f"{value:.10g}"
    return value


def write_csv(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        for r in rows:
            writer.writerow([_cell(r[c]) for c in COLUMNS])


def read_csv(path):
    """Read history.csv back (numbers become floats, empty stays '')."""
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            for c in NUMERIC:
                rec[c] = float(rec[c]) if rec[c] != "" else ""
            out.append(rec)
    return out


def build_history(root=ROOT):
    root = Path(root)
    rows = build_rows(root / "data" / "raw", load_sources(root / "sources.json"))
    write_csv(rows, root / "data" / "history.csv")
    return rows


def main(argv=None):
    rows = build_history()
    print(f"data/history.csv: {len(rows)} rows from {len(list_days(ROOT / 'data' / 'raw'))} days")


if __name__ == "__main__":
    sys.exit(main())
