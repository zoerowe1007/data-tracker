"""Checks on the files of the repository itself: sources, site pages, README and secrets."""
import json
import re
import subprocess
import shutil
from pathlib import Path

import pytest

from tracker.common import COLUMNS, NUMERIC, ROOT, load_sources
from tracker.convert import CONVERTERS

README = (ROOT / "README.md").read_text(encoding="utf-8")


def test_sources_are_valid():
    sources = load_sources()
    assert len(sources) >= 2
    names = [s["name"] for s in sources]
    assert len(set(names)) == len(names)
    ids = []
    for s in sources:
        assert s["kind"] in CONVERTERS and s["format"] in ("csv", "json")
        assert s["headline"] in NUMERIC
        assert len(s["items"]) >= 10, s["name"]  # at least ten items per source
        for it in s["items"]:
            assert it["id"] and it["item"]
        ids += [it["id"] for it in s["items"]]
    assert len(set(ids)) == len(ids)  # item_id is unique across sources, so (date, item_id) is a key
    assert len(ids) >= 10


def test_headline_columns_match_between_python_and_the_site():
    js = (ROOT / "assets" / "common.js").read_text(encoding="utf-8")
    block = re.search(r"DT\.HEADLINE = \{(.*?)\};", js, re.S).group(1)
    site = dict(re.findall(r"(\w+):\s*'(\w+)'", block))
    assert site == {s["name"]: s["headline"] for s in load_sources()}
    numeric = re.search(r"DT\.NUMERIC = \[(.*?)\];", js, re.S).group(1)
    assert re.findall(r"'(\w+)'", numeric) == NUMERIC


def test_every_page_shares_one_navigation_bar_and_stylesheet():
    navs, sheets = set(), set()
    for page in ("index.html", "browse.html", "trends.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        nav = re.search(r'<nav aria-label="Main">.*?</nav>', html, re.S).group(0)
        navs.add(re.sub(r'\s*aria-current="page"', "", nav))
        sheets.add(re.search(r'<link rel="stylesheet" href="([^"]+)"', html).group(1))
        assert 'rel="manifest"' in html and html.count('aria-current="page"') == 1
    assert len(navs) == 1 and sheets == {"assets/style.css"}


def test_the_manifest_and_service_worker_are_in_place():
    manifest = json.loads((ROOT / "manifest.webmanifest").read_text())
    assert manifest["display"] == "standalone" and manifest["start_url"]
    assert {i["sizes"] for i in manifest["icons"]} >= {"192x192", "512x512"}
    for icon in manifest["icons"]:
        assert (ROOT / icon["src"]).exists()
    sw = (ROOT / "sw.js").read_text()
    for page in ("index.html", "browse.html", "trends.html", "data/history.csv", "data/status.json"):
        assert f"'{page}'" in sw


def test_the_pages_load_only_the_two_data_files():
    js = (ROOT / "assets" / "common.js").read_text()
    assert "data/history.csv" in js and "data/status.json" in js
    assert len(re.findall(r"data/[\w.]+", js)) == 2


def test_readme_lists_every_column_file_and_source():
    for col in COLUMNS:
        assert f"| `{col}` |" in README, col
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if path.is_file() and re.match(r"^(tracker/\w+\.py|assets/\w+\.(js|css)|index\.html|browse\.html|trends\.html|"
                                       r"sw\.js|manifest\.webmanifest|sources\.json|\.github/workflows/[\w.]+)$", rel):
            assert rel.split("/")[-1] in README or rel in README, rel
    for s in load_sources():
        assert f"`{s['name']}`" in README
    assert "python -m tracker.history" in README
    assert "move %" in README and "tests.yml/badge.svg" in README


def test_no_secrets_in_the_repository():
    pattern = re.compile(r"(api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}", re.I)
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in (".py", ".js", ".json", ".yml", ".html", ".md") and ".git/" not in str(path):
            assert not pattern.search(path.read_text(encoding="utf-8", errors="ignore")), path


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_trends_numbers_match_the_python_reference():
    res = subprocess.run(["node", str(ROOT / "tests" / "trends_check.mjs")], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout + res.stderr


def test_workflow_files_are_valid_yaml():
    yaml = pytest.importorskip("yaml")
    files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert len(files) == 3
    for f in files:
        doc = yaml.safe_load(f.read_text(encoding="utf-8"))
        assert doc["jobs"], f
