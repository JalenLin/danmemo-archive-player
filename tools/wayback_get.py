"""Download the JP in-game notice ("お知らせ") material that the Wayback Machine knows about.

  images: cdn-danmemo.akamaized.net/webview/production/notice/img/<md5>.<ext> — official JP announcement
          art (2019-2024). Still served by the CDN; the Wayback copy is the fallback. md5-verified.
  pages:  the JP notice pages that referenced them (titles / bodies / image links), from Wayback only
          (the API hosts are gone). Fetched slowly to be gentle with archive.org.

Output: wayback/img/<md5>.<ext>, wayback/pages/<host>/<name>.html, wayback/pages/index.json.
Resumable; re-running only fetches what is missing.
Usage: python tools/wayback_get.py [images|pages|all]
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "wayback")
CDN = "https://cdn-danmemo.akamaized.net/"
UA = {"User-Agent": "danmemo-archive-player (personal archive; contact via project owner)"}
PAGE_HOSTS = ["news-danmemo.wfs.games/external/notice/*", "api-danmemo.wrightflyer.net/asset/notice/*"]


def fetch(url, timeout=60, tries=4, wait=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404) or i == tries - 1:
                raise
            time.sleep(wait * (i + 1))  # 429 / 5xx: back off
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def cdx(pattern, name):
    """Wayback capture list (one row per distinct URL, status 200), cached in wayback/."""
    path = os.path.join(OUT, f"cdx_{name}.txt")
    if not os.path.exists(path):
        q = urllib.parse.urlencode({"url": pattern, "fl": "original,timestamp,mimetype,length",
                                    "filter": "statuscode:200", "collapse": "urlkey", "limit": 200000})
        # the CDX server answers 503 under load: be patient (up to ~15 min of retries)
        data = fetch(f"http://web.archive.org/cdx/search/cdx?{q}", timeout=300, tries=8, wait=30)
        open(path, "wb").write(data)
    return [l.split() for l in open(path, encoding="utf-8") if l.strip()]


def get_image(row):
    url, ts = row[0], row[1]
    name = url.rsplit("/", 1)[1]
    dst = os.path.join(OUT, "img", name)
    md5 = name.split(".")[0]
    if os.path.exists(dst):
        return "skip"
    for src in (CDN + "webview/production/notice/img/" + name, f"http://web.archive.org/web/{ts}id_/{url}"):
        try:
            data = fetch(src)
        except Exception:
            continue
        if hashlib.md5(data).hexdigest() == md5:
            open(dst + ".tmp", "wb").write(data)
            os.replace(dst + ".tmp", dst)
            return "cdn" if src.startswith(CDN) else "wayback"
    return "fail"


def images():
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    rows = cdx("cdn-danmemo.akamaized.net/webview/production/notice/img/*", "notice_img")
    rows = [r for r in rows if re.search(r"/img/[0-9a-f]{32}\.\w+$", r[0])]
    print("notice images:", len(rows), flush=True)
    from collections import Counter
    stats = Counter()
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, s in enumerate(ex.map(get_image, rows), 1):
            stats[s] += 1
            if i % 500 == 0:
                print(f"  {i}/{len(rows)} {dict(stats)}", flush=True)
    print("images done", dict(stats), flush=True)


def page_key(url):
    """One file per notice: drop cache-buster query params, keep identifying ones (ids)."""
    u = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query) if k not in ("timestamp", "q", "t", "_")]
    tail = u.path.strip("/").replace("/", "_") + ("_" + "_".join(f"{k}-{v}" for k, v in sorted(q)) if q else "")
    return u.netloc, re.sub(r"[^\w.-]", "_", tail)[:180]


def pages():
    rows = []
    for i, pat in enumerate(PAGE_HOSTS):
        rows += cdx(pat, f"pages{i}")
    best = {}
    for r in rows:  # keep the latest capture of each notice
        k = page_key(r[0])
        if k not in best or r[1] > best[k][1]:
            best[k] = r
    idx_path = os.path.join(OUT, "pages", "index.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    todo = [(k, r) for k, r in sorted(best.items()) if f"{k[0]}/{k[1]}" not in index]
    print("notice pages:", len(best), "to fetch:", len(todo), flush=True)
    # archive.org answers slowly (~20s per capture) rather than refusing, so a few parallel requests
    # are what makes this finish; each worker still pauses between its own requests
    import threading
    lock = threading.Lock()
    done = [0, 0]  # fetched, failed

    def one(item):
        (host, name), r = item
        url, ts = r[0], r[1]
        try:
            # CDX keeps some URLs HTML-escaped ("&amp;"), which the archive answers with 404
            data = fetch(f"http://web.archive.org/web/{ts}id_/{url.replace('&amp;', '&')}", timeout=120)
        except Exception as e:
            with lock:
                done[1] += 1
                print("  fail", url, e, flush=True)
            return
        d = os.path.join(OUT, "pages", host)
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, name + ".html"), "wb").write(data)
        with lock:
            index[f"{host}/{name}"] = {"url": url, "timestamp": ts, "file": f"{host}/{name}.html"}
            done[0] += 1
            if done[0] % 50 == 0:
                json.dump(index, open(idx_path, "w"), ensure_ascii=False, indent=0)
                print(f"  {done[0] + done[1]}/{len(todo)} fails={done[1]}", flush=True)
        time.sleep(1.0)

    # WB_WORKERS=1 for a gentle retry pass over the failures
    with ThreadPoolExecutor(max_workers=int(os.environ.get("WB_WORKERS", 4))) as ex:
        list(ex.map(one, todo))
    fails = done[1]
    json.dump(index, open(idx_path, "w"), ensure_ascii=False, indent=0)
    print("pages done", len(index), "fails", fails, flush=True)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(os.path.join(OUT, "pages"), exist_ok=True)
    if what in ("images", "all"):
        images()
    if what in ("pages", "all"):
        pages()
