"""Download helper (standard library only): returns the response bytes exactly as received."""
import gzip
import time
import urllib.error
import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; data-tracker/1.0; student project)"


class HttpError(Exception):
    """A download that failed after retries."""


def fetch_bytes(url, timeout=45, retries=3, sleep=time.sleep):
    """GET `url`. Retries on network errors, 429 and 5xx with a growing pause."""
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "gzip"}
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    payload = gzip.decompress(payload)
                return payload
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} from {url.split('?')[0]}"
            if e.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = f"{type(e).__name__}: {e} ({url.split('?')[0]})"
        if attempt < retries - 1:
            sleep(3 * 2 ** attempt)
    raise HttpError(last or f"request failed: {url}")
