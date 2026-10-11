"""Fetch the asset manifests of old JP online builds (pre-md5 CDN scheme) from their APKs.

Old clients (e.g. 8.2.0, 2019) bundle a manifest whose remoteManifestUrl points at
<CDN>/<sha1>/png/production/project.manifest.N; those are still served, and every asset entry
carries its own <sha1>/contents/<path> URL plus md5 — Japanese originals of banners, name plates,
CGs and voices the memorial app's manifest no longer lists. Newer builds (10.x+) use the md5
scheme with deleted manifests, so only pre-md5 APKs help.

Other regions' old builds (e.g. Traditional Chinese com.tw.danmemo 5.x) use <CDN>/<region>/<sha1>/png/
production-<region>/…; those go to cdn/legacy_<region>/ and are kept apart from the JP set.

Usage: python tools/legacy_manifests.py some_old.apk [more.apk/.xapk ...]
Writes cdn/legacy/<app version>/png.project.manifest.N for JP builds (read by fill_gaps.py),
cdn/legacy_<region>/<app version>/ for others.
"""
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "cdn", "legacy")


def bundled_manifest(path):
    """(app version or None, bundled manifest dict) from an .apk or an .xapk (zip of apks)."""
    z = zipfile.ZipFile(path)
    names = z.namelist()
    for n in names:
        if re.fullmatch(r"assets/(\w+/)?manifest/bundled_png\.manifest", n):
            return json.loads(z.read(n))
    for n in names:  # xapk: look inside the base apk
        if n.endswith(".apk"):
            m = bundled_manifest(io.BytesIO(z.read(n)))
            if m:
                return m
    return None


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "CocosDownloader"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for apk in sys.argv[1:]:
        m = bundled_manifest(apk)
        if not m:
            print(apk, ": no bundled manifest")
            continue
        url = m.get("remoteManifestUrl", "")
        old = re.match(r"(https://[^/]+/(?:(\w+)/)?([0-9a-f]{40})/png/production[\w-]*/)project\.manifest\.1$", url)
        if not old:
            print(apk, ": md5-scheme build (manifest", m.get("version", "?"), ") — its manifests are gone, skipped")
            continue
        base, region, sha = old.groups()
        ver = re.search(r"_(\d+(?:\.\d+)+)", os.path.basename(apk))
        name = ver.group(1) if ver else sha[:10]
        d = os.path.join(OUT if not region else f"{OUT}_{region}", name)
        os.makedirs(d, exist_ok=True)
        n_assets = 0
        for n in range(1, 10):
            try:
                data = get(f"{base}project.manifest.{n}")
            except urllib.error.HTTPError:
                break
            n_assets += len(json.loads(data).get("assets", {}))
            open(os.path.join(d, f"png.project.manifest.{n}"), "wb").write(data)
        print(f"{apk}: {region or 'jp'} build {name} ({sha[:10]}…) → {d}  {n_assets} assets")


if __name__ == "__main__":
    main()
