"""The raw files: data/raw/<UTC date>/<source>.<format>.gz, exactly the bytes the source returned."""
import gzip
import re
import shutil
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def raw_path(raw_dir, date, source, fmt):
    return Path(raw_dir) / date / f"{source}.{fmt}.gz"


def write_raw(raw_dir, date, source, fmt, payload):
    """Compress `payload` (bytes). The gzip timestamp is fixed so equal data gives equal files."""
    path = raw_path(raw_dir, date, source, fmt)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(payload)
    return path


def read_raw(path):
    with gzip.open(path, "rb") as fh:
        return fh.read()


def clear_day(raw_dir, date):
    """A second run on the same UTC day replaces that day's raw files."""
    shutil.rmtree(Path(raw_dir) / date, ignore_errors=True)


def list_days(raw_dir):
    """{date: {source: path}} for every raw file, dates ascending."""
    root = Path(raw_dir)
    days = {}
    if not root.is_dir():
        return days
    for day_dir in sorted(root.iterdir()):
        if not (day_dir.is_dir() and DATE_RE.match(day_dir.name)):
            continue
        files = {}
        for p in sorted(day_dir.glob("*.gz")):
            parts = p.name[:-3].rsplit(".", 1)  # <source>.<format>
            if len(parts) == 2:
                files[parts[0]] = p
        if files:
            days[day_dir.name] = files
    return days
