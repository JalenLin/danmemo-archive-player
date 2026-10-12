"""Download extra assets listed in a manifest-style JSON {logical_path: {md5, path, size}} into assets/.
Usage: python tools/download_extra.py <list.json> [workers]   (uses download.fetch: resumable, md5-checked)"""
import json, sys
from concurrent.futures import ThreadPoolExecutor
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import download

items = json.load(open(sys.argv[1], encoding="utf-8"))
workers = int(sys.argv[2]) if len(sys.argv) > 2 else 12
with ThreadPoolExecutor(workers) as ex:
    res = list(ex.map(lambda kv: download.fetch(*kv), items.items()))
fails = [k for (k, _), (st, _) in zip(items.items(), res) if st.startswith("fail")]
print(len(items), "files;", sum(1 for st, _ in res if st == "ok"), "downloaded;", len(fails), "failed", fails[:10])
