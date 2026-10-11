"""Download files listed by gdrive_ls.py (name<TAB>id per line) from a public Drive folder.

Usage: python gdrive_get.py <list.txt> <out_dir> [workers]
Resumable (skips existing non-empty files). Uses the public uc?export=download endpoint.
"""
import html
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def _confirm_url(page):
    """Large files get a "can't scan for viruses" page; its form carries the real download URL."""
    m = re.search(r'<form[^>]+action="([^"]+)"', page)
    if not m:
        return None
    params = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', page))
    return html.unescape(m.group(1)) + "?" + urllib.parse.urlencode(params)


def get(name, fid, out):
    dst = os.path.join(out, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return "skip"
    for attempt in range(6):
        try:
            url = f"https://drive.google.com/uc?export=download&id={fid}"
            for _ in range(2):
                r = urllib.request.urlopen(url, timeout=120)
                head = r.read(65536)
                if not (head[:15].lower().startswith(b"<!doctype html") or head[:5] == b"<html"):
                    break
                nxt = _confirm_url((head + r.read()).decode("utf-8", "replace"))
                r.close()
                if not nxt:
                    raise IOError("got html (quota/confirm page)")
                url = nxt
            else:
                raise IOError("got html after confirm")
            with open(dst + ".part", "wb") as f:  # stream: some files are hundreds of MB
                f.write(head)
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            r.close()
            os.replace(dst + ".part", dst)
            return "ok"
        except Exception as e:
            err = e
            time.sleep(3 * (attempt + 1))
    return f"fail {err!r}"


def main():
    lst, out = sys.argv[1], sys.argv[2]
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    os.makedirs(out, exist_ok=True)
    rows = [l.rstrip("\n").split("\t") for l in open(lst, encoding="utf-8") if "\t" in l and not l.split("\t")[0].endswith("/")]
    fails = []
    with ThreadPoolExecutor(workers) as ex:
        for i, ((name, fid), st) in enumerate(zip(rows, ex.map(lambda r: get(r[0], r[1], out), rows))):
            if st.startswith("fail"):
                fails.append((name, st))
            if (i + 1) % 500 == 0:
                print(f"{i + 1}/{len(rows)} fails={len(fails)}", flush=True)
    print(f"done {len(rows)} fails={len(fails)}")
    for f in fails[:20]:
        print(f)


if __name__ == "__main__":
    main()
