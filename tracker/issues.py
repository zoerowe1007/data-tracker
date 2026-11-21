"""One GitHub Issue per day, titled with the date. It lists the biggest moves since the previous run
(old value, new value, percent), every item that appeared or disappeared, and the state of each source.
The previous day's Issue is closed. It is opened every day, even when nothing changed. Uses the `gh` CLI."""
import json
import os
import subprocess

from .analysis import biggest_moves, compare

LABEL = "data-tracker"
MOVES_LISTED = 10


def fmt(x):
    if x == "" or x is None:
        return "—"
    ax = abs(x)
    if ax >= 1e6:
        return f"{x:,.0f}"
    if ax >= 1000:
        return f"{x:,.2f}"
    if ax >= 1:
        return f"{x:.2f}"
    return f"{x:.4f}"


def build_issue(date, rows, sources, results, status, site_url=""):
    """Return (title, body). The title is the date."""
    diff = compare(rows, sources)
    moves = biggest_moves(diff["changes"], MOVES_LISTED)
    ok = [s for s in results if s["ok"]]
    bad = [s for s in results if not s["ok"]]
    lines = [f"Run {status['run_time']} · {len(ok)}/{len(results)} sources ok · {status['items']} items · "
             f"**{status['new_today']} appeared** · **{status['gone_today']} disappeared**", ""]
    if site_url:
        lines += [f"Site: {site_url}", ""]
    if bad:
        lines += ["## Sources that failed", ""] + [f"- `{s['name']}`: {s.get('error', 'failed')}" for s in bad] + [""]
    compared = [c for c in diff["changes"] if c["old"] != ""]
    lines += [f"## Biggest moves since the previous run (top {MOVES_LISTED} by percent change)", ""]
    if not compared:
        lines += ["No previous run to compare with yet: today's values are the starting point.", ""]
    elif all(not c["pct"] for c in compared) and not diff["new"] and not diff["gone"]:
        lines += ["No changes since the previous run: every tracked value is the same.", ""]
    else:
        lines += ["| Item | Source | Old | New | Change |", "|---|---|---:|---:|---:|"]
        for m in moves:
            lines.append(f"| {m['item']} | {m['source']} | {fmt(m['old'])} | {fmt(m['new'])} | {m['pct']:+.2f}% |")
        lines.append("")
    lines += [f"## Appeared ({len(diff['new'])})", ""]
    lines += [f"- {r['item']} ({r['source']})" for r in diff["new"]] or ["None."]
    lines += ["", f"## Disappeared ({len(diff['gone'])})", ""]
    lines += [f"- {r['item']} ({r['source']})" for r in diff["gone"]] or ["None."]
    lines += ["", "_A move is the percent change of an item's headline value (price for crypto, "
              "temperature in °F for weather, US air quality index for air) since that source's previous run._", ""]
    return date, "\n".join(lines)


def _gh(*args, input_text=None):
    res = subprocess.run(["gh", *args], input=input_text, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {res.stderr.strip() or res.stdout.strip()}")
    return res.stdout


def publish(title, body, repo=None):
    """Create (or update) the Issue titled `title` and close every other open data-tracker Issue."""
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    base = ["--repo", repo] if repo else []
    _gh("label", "create", LABEL, "--color", "a8336e", "--description", "Daily data tracker report", "--force", *base)
    found = json.loads(_gh("issue", "list", "--state", "all", "--label", LABEL, "--limit", "200",
                           "--json", "number,title,state", *base) or "[]")
    mine = [i for i in found if i["title"] == title]
    if mine:
        number = mine[0]["number"]
        _gh("issue", "edit", str(number), "--body-file", "-", *base, input_text=body)
        if mine[0]["state"] != "OPEN":
            _gh("issue", "reopen", str(number), *base)
    else:
        out = _gh("issue", "create", "--title", title, "--body-file", "-", "--label", LABEL, *base, input_text=body)
        number = int(out.strip().rsplit("/", 1)[-1])
    for i in found:
        if i["state"] == "OPEN" and i["title"] != title:
            _gh("issue", "close", str(i["number"]), "--comment", f"Superseded by the {title} report.", *base)
    return number
