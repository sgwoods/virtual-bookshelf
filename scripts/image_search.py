"""Pictures of a book from the web, for the review page — no tab switching.

The review page shows these as a grid beside the options; one click fetches
the full image into Downloads (with its source, via local_images.grab) and it
appears among "your images", auto-cropped, used for the book you decide on.

Sources, in order: Bing Images (its results page carries each picture's full
address, the page it is on, and a thumbnail), then DuckDuckGo Images. Google
Images does not allow this (it refuses to be shown inside another page and
does not offer its results to programs), so it stays a link.

Results are cached per query in data/cache/images/. Standard library only.
"""
from __future__ import annotations

import hashlib, html, json, re, time, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/cache/images"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")
TTL = 14 * 24 * 3600


def _get(url: str, referer: str = "", timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.8",
                                               **({"Referer": referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(3_000_000).decode("utf-8", "replace")


def _ok(u: str) -> bool:
    return urllib.parse.urlparse(u or "").scheme in ("http", "https")


def parse_bing(text: str) -> list[dict]:
    """Bing's results: each picture's link carries m="{json}" with murl (the
    image), purl (its page), turl (thumbnail) and t (title)."""
    out = []
    for raw in re.findall(r'\bm="(\{[^"]*?\})"', text):
        try:
            m = json.loads(html.unescape(raw))
        except ValueError:
            continue
        if _ok(m.get("murl")):
            out.append({"image": m["murl"], "page": m.get("purl", ""), "thumb": m.get("turl") or m["murl"],
                        "title": html.unescape(m.get("t", "")).replace("", "").replace("", "")})
    return out


def bing(q: str, n: int = 30) -> list[dict]:
    url = ("https://www.bing.com/images/async?" +
           urllib.parse.urlencode({"q": q, "first": 0, "count": n, "mmasync": 1, "adlt": "strict"}))
    return parse_bing(_get(url))


def parse_ddg_token(text: str) -> str:
    m = re.search(r"""vqd=["']?([\d-]+)""", text)
    return m.group(1) if m else ""


def parse_ddg(data: dict) -> list[dict]:
    out = []
    for r in (data or {}).get("results", []):
        if _ok(r.get("image")):
            out.append({"image": r["image"], "page": r.get("url", ""), "thumb": r.get("thumbnail") or r["image"],
                        "title": r.get("title", ""), "w": r.get("width"), "h": r.get("height")})
    return out


def ddg(q: str) -> list[dict]:
    token = parse_ddg_token(_get("https://duckduckgo.com/?" + urllib.parse.urlencode({"q": q, "iax": "images",
                                                                                         "ia": "images"})))
    if not token:
        return []
    url = "https://duckduckgo.com/i.js?" + urllib.parse.urlencode(
        {"l": "us-en", "o": "json", "q": q, "vqd": token, "f": ",,,,,", "p": "1"})
    return parse_ddg(json.loads(_get(url, referer="https://duckduckgo.com/")))


def search(q: str, n: int = 30) -> dict:
    """{"query", "source", "results": [{image, page, thumb, title, host}], "error"}."""
    q = " ".join((q or "").split())[:200]
    if not q:
        return {"query": q, "source": "", "results": [], "error": "nothing to search for"}
    f = CACHE / (hashlib.sha1(q.lower().encode()).hexdigest() + ".json")
    if f.exists() and time.time() - f.stat().st_mtime < TTL:
        try:
            return json.loads(f.read_text())
        except ValueError:
            pass
    errors = []
    for name, fn in (("Bing", bing), ("DuckDuckGo", ddg)):
        try:
            found = fn(q)
        except Exception as e:                      # blocked, offline, page changed
            errors.append(f"{name}: {e}")
            continue
        if found:
            seen, results = set(), []
            for r in found:
                if r["image"] not in seen:
                    seen.add(r["image"])
                    h = urllib.parse.urlparse(r["page"] or r["image"]).hostname or ""
                    results.append({**r, "host": h[4:] if h.startswith("www.") else h})
            out = {"query": q, "source": name, "results": results[:n], "error": ""}
            CACHE.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(out))
            return out
        errors.append(f"{name}: no results")
    return {"query": q, "source": "", "results": [], "error": "; ".join(errors)}
