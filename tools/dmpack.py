"""Pack the built player for the Android app: python tools/dmpack.py [OUT.dmpack]   (default DanMemo.dmpack)

Builds on a computer are much faster than on a phone, and one big file copies to a phone much faster than the
hundreds of thousands of files of an extracted backup. The pack is one zip of the built player (web/) and only
the assets it uses; put it in the phone's DanMemo folder and the app plays from it, with nothing to set up.

The pack holds your own game data: it is for your own devices, don't share it.

Assets: every r/<i>/... path in the built data, plus what the player derives from those paths — the files next
to each .lwf (its textures) and the files a path is the prefix of (portrait faces: <base>.*). Media are stored
uncompressed (the app reads them at their offset in the pack), the rest is deflated.
"""
import collections
import os
import re
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

STORED = (".ogg", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".lwf", ".woff2")
REF = re.compile(r'"(r/(\d+)/[^"]*)"')
# Files are read ahead in parallel: on Windows the antivirus scans each file as it is opened, and one at a time
# those waits add up over ~200,000 files. The pack is still written in order by one thread.
READERS = 16
AHEAD = 256 << 20  # bytes read ahead at most
BIG = 32 << 20     # larger files (movies) are streamed by the writer itself


def read(path, mode="rb"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        return f.read()


def walk(top):
    for dp, _, fs in os.walk(top):
        for f in fs:
            yield os.path.join(dp, f)


PLAYER = ("index.html", "transparent.png", "js", "css", "vendor", "data")  # as the app bundles them (build.gradle.kts)


def player_files(web):
    """web/ as it is served: the player's own files and its built data (not r/, the asset roots, nor dev files)"""
    out = {}
    for name in os.listdir(web):
        p = os.path.join(web, name)
        if name not in PLAYER:
            continue
        if os.path.isdir(p):
            for f in walk(p):
                out[os.path.relpath(f, web).replace(os.sep, "/")] = f
        else:
            out[name] = p
    return out


def assets(roots, data):
    """web path -> disk path of the assets the built data refers to; and the paths not found"""
    out, missing = {}, []

    def add(i, disk):
        out.setdefault(f"r/{i}/" + os.path.relpath(disk, roots[i]).replace(os.sep, "/"), disk)

    refs = set()
    with ThreadPoolExecutor(READERS) as ex:
        for text in ex.map(lambda f: read(f, "r"), [f for f in walk(data) if f.endswith(".json")]):
            refs.update(REF.findall(text))
    for ref, i in sorted(refs):
        i = int(i)
        if i >= len(roots):
            missing.append(ref)
            continue
        p = os.path.join(roots[i], *ref.split("/")[2:])
        if os.path.isfile(p):
            add(i, p)
            if p.endswith(".lwf"):  # its textures sit next to it
                d = os.path.dirname(p)
                for f in os.listdir(d):
                    if os.path.isfile(os.path.join(d, f)):
                        add(i, os.path.join(d, f))
        elif os.path.isdir(p):
            for f in walk(p):
                add(i, f)
        else:  # a prefix (portrait base -> <base>.body.png, <base>.<face>.png, …)
            d, base = os.path.split(p)
            hits = [os.path.join(d, f) for f in os.listdir(d) if f.startswith(base)] if os.path.isdir(d) else []
            hits = [f for f in hits if os.path.isfile(f)]
            for f in hits:
                add(i, f)
            if not hits:
                missing.append(ref)
    return out, missing


def main(argv=None):
    argv = sys.argv if argv is None else argv
    dst = os.path.abspath(argv[1] if len(argv) > 1 else "DanMemo.dmpack")
    if not dst.lower().endswith(".dmpack"):
        dst += ".dmpack"
    cfg = config.load()
    web = cfg["web"]
    data = os.path.join(web, "data")
    if not os.path.exists(os.path.join(data, "index.json")):
        print("The player isn't built yet: build it first (tools/build_web.py, or the setup page).", flush=True)
        return 1
    files = player_files(web)
    found, missing = assets(cfg["asset_roots"], data)
    files.update(found)
    usm = sorted(os.path.basename(n) for n in found if n.endswith(".usm"))
    if usm:  # a build from before the movies were converted (v1.0.0), or without ffmpeg
        print(f"Note: {len(usm)} cutscene movies aren't converted ({', '.join(usm[:3])}{', …' if len(usm) > 3 else ''}): "
              "the player can't show .usm. Rebuild (with ffmpeg) to convert them, then pack again.", flush=True)
    size = {f: os.path.getsize(f) for f in files.values()}
    total = sum(size.values())
    print(f"{len(files)} files, {total / 1e9:.2f} GB" +
          (f"; {len(missing)} referenced paths not found (the player shows those as missing too)" if missing else ""),
          flush=True)
    tmp = dst + ".part"
    done, shown, t0 = 0, -1, time.time()
    items = sorted(files.items())
    with zipfile.ZipFile(tmp, "w", allowZip64=True) as z, ThreadPoolExecutor(READERS) as ex:
        queue, ahead, nxt = collections.deque(), 0, 0
        for i, (name, path) in enumerate(items):
            while nxt < len(items) and (nxt <= i or (ahead < AHEAD and len(queue) < READERS * 8)):
                p = items[nxt][1]
                small = size[p] <= BIG
                queue.append(ex.submit(read, p) if small else None)
                ahead += size[p] if small else 0
                nxt += 1
            kind = zipfile.ZIP_STORED if name.lower().endswith(STORED) else zipfile.ZIP_DEFLATED
            job = queue.popleft()
            if job is None:
                z.write(path, name, compress_type=kind)
            else:
                info = zipfile.ZipInfo.from_file(path, name)
                info.compress_type = kind
                z.writestr(info, job.result())
                ahead -= size[path]
            done += size[path]
            pct = int(100 * done / max(total, 1)) // 5 * 5
            if pct != shown:
                print(f"  {pct}%", flush=True)
                shown = pct
    os.replace(tmp, dst)
    print(f"Wrote {dst} ({os.path.getsize(dst) / 1e9:.2f} GB, {time.time() - t0:.0f} s).\n"
          "Copy it to the DanMemo folder of the phone's storage; the app then opens the player from it.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
