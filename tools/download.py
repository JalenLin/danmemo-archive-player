"""Download DanMemo assets from the original CDN into assets/<logical path>.

Resumable: files whose size+md5 already match are skipped. Writes a log of failures.
Usage: python download.py [--workers N]
"""
import argparse
import re
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

ROOT = config.ROOT
CDN = re.search(rb"https://cdn-[\w.-]+\.akamaized\.net", open(config.load()["libapp"], "rb").read()).group(0).decode() + "/"
MAN = f"{ROOT}/cdn"
OUT = f"{ROOT}/assets"


def jobs():
    seen = {}
    names = sorted((f for f in os.listdir(MAN) if f.startswith("project.manifest")), key=lambda f: (len(f), f))
    for name in names:
        for k, v in json.load(open(f"{MAN}/{name}"))["assets"].items():
            if k.startswith("manifests/"):
                continue
            seen[k] = v
    for v in json.load(open(f"{MAN}/manifests/single_image.manifest"))["singleImages"].values():
        k = v["path"].split("/", 1)[1].rsplit("/", 1)[0]  # files/ui/single_image/<id>.jpg
        seen.setdefault(k, v)
    for v in json.load(open(f"{MAN}/manifests/voice_episode.manifest"))["episodes"].values():
        k = v["path"].split("/", 1)[1].rsplit("/", 1)[0]  # files/sound/voice_episode_zip/<id>.zip
        seen.setdefault(k, v)
    return seen


def md5file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(k, v):
    dst = os.path.join(OUT, k)
    if os.path.exists(dst) and os.path.getsize(dst) == v["size"] and md5file(dst) == v["md5"]:
        return "skip", v["size"]
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + ".part"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(CDN + v["path"], timeout=60) as r, open(tmp, "wb") as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            if md5file(tmp) != v["md5"]:
                raise IOError("md5 mismatch")
            os.replace(tmp, dst)
            return "ok", v["size"]
        except Exception as e:
            err = e
            time.sleep(2 * (attempt + 1))
    return f"fail {err!r}", 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    js = jobs()
    total = sum(v["size"] for v in js.values())
    print(f"{len(js)} files, {total / 1e9:.2f} GB", flush=True)
    done = 0
    nbytes = 0
    fails = []
    lock = threading.Lock()
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(fetch, k, v): k for k, v in js.items()}
        for fu in as_completed(futs):
            st, sz = fu.result()
            with lock:
                done += 1
                nbytes += sz
                if st.startswith("fail"):
                    fails.append((futs[fu], st))
                if done % 2000 == 0 or done == len(js):
                    el = time.time() - t0
                    print(f"{done}/{len(js)} files, {nbytes / 1e9:.2f}/{total / 1e9:.2f} GB, "
                          f"{el / 60:.1f} min, fails={len(fails)}", flush=True)
    with open(f"{ROOT}/cdn/download_failures.txt", "w") as f:
        for k, st in fails:
            f.write(f"{k}\t{st}\n")
    print("done; failures:", len(fails), flush=True)


if __name__ == "__main__":
    sys.exit(main())
