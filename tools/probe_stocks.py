"""Tries several no-login stock quote endpoints and records what each one answers.
Run by the `probe stocks` workflow (GitHub Actions has internet); writes tools/probe_stocks.json."""
import json
import time
import urllib.error
import urllib.request

UA_BROWSER = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ALL = "+".join(s + ".us" for s in "wmt tsn t aal luv txn cof jpm schw wfc tm xom kmb mck jbht".split())
CANDIDATES = {
    "stooq_com_many": f"https://stooq.com/q/l/?s={ALL}&f=sd2t2ohlcv&h&e=csv",
    "stooq_com_one": "https://stooq.com/q/l/?s=wmt.us&f=sd2t2ohlcv&h&e=csv",
    "stooq_com_one_nofmt": "https://stooq.com/q/l/?s=wmt.us&i=d",
    "stooq_pl_one": "https://stooq.pl/q/l/?s=wmt.us&f=sd2t2ohlcv&h&e=csv",
    "stooq_daily_history": "https://stooq.com/q/d/l/?s=wmt.us&i=d",
    "yahoo_chart_wmt": "https://query1.finance.yahoo.com/v8/finance/chart/WMT?range=5d&interval=1d",
    "yahoo_chart2_wmt": "https://query2.finance.yahoo.com/v8/finance/chart/WMT?range=5d&interval=1d",
    "yahoo_quote_many": "https://query1.finance.yahoo.com/v7/finance/quote?symbols=WMT,JPM,T",
    "yahoo_spark_many": "https://query1.finance.yahoo.com/v8/finance/spark?symbols=WMT,JPM,T&range=5d&interval=1d",
    "nasdaq_quote": "https://api.nasdaq.com/api/quote/WMT/info?assetclass=stocks",
    "cboe_delayed": "https://cdn.cboe.com/api/global/delayed_quotes/quotes/WMT.json",
    "cboe_delayed_idx": "https://cdn.cboe.com/api/global/delayed_quotes/quotes/_SPX.json",
}


def attempt(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            return {"status": r.status, "bytes": len(body), "head": body[:300].decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "error": str(e), "head": e.read()[:200].decode("utf-8", "replace")}
    except Exception as e:  # network error, timeout, TLS
        return {"error": f"{type(e).__name__}: {e}"}


def main():
    out = {}
    for name, url in CANDIDATES.items():
        out[name] = {"url": url, "python_ua": attempt(url, "Python-urllib/3.12"),
                     "browser_ua": attempt(url, UA_BROWSER)}
        time.sleep(1)
    with open("tools/probe_stocks.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    for name, r in out.items():
        print(name, r["python_ua"].get("status") or r["python_ua"].get("error"),
              r["browser_ua"].get("status") or r["browser_ua"].get("error"))


if __name__ == "__main__":
    main()
