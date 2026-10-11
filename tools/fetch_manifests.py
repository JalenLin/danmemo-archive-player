"""Fetch the CDN asset manifests used by the game (into cdn/).

The CDN host and manifest version are read from the user's own libapp.so (config.json "libapp").
Fetches project.manifest.1..N (until the CDN stops answering) plus the sub-manifests they list.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

cfg = config.load()
OUT = config.load()["cdn"]
data = open(cfg["libapp"], "rb").read()
host = re.search(rb"https://cdn-[\w.-]+\.akamaized\.net", data).group(0).decode()
m = re.search(rb'"remoteManifestUrl": "\{\}/(manifests/(\w+)/(\w+))/project\.manifest\.1/([0-9a-f]{32})"', data)
base, version = m.group(1).decode(), m.group(4).decode()
print("CDN", host, "manifests", base, "version", version)


def get(path):
    with urllib.request.urlopen(f"{host}/{path}", timeout=60) as r:
        return r.read()


os.makedirs(os.path.join(OUT, "manifests"), exist_ok=True)
names = ["project.manifest"]
n = 1
while True:
    try:
        body = get(f"{base}/project.manifest.{n}/{version}")
    except urllib.error.HTTPError:
        break
    fn = "project.manifest" if n == 1 else f"project.manifest.{n}"
    open(os.path.join(OUT, fn), "wb").write(body)
    print("got", fn, len(body))
    n += 1

for k, v in json.load(open(os.path.join(OUT, "project.manifest")))["assets"].items():
    if k.startswith("manifests/"):
        open(os.path.join(OUT, k), "wb").write(get(v["path"]))
        print("got", k)
