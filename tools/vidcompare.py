"""Compare the web player with a recording of the original game, line by line.

  capture  play stories in skip mode and screenshot the stage at every dialogue / narration line
  align    sample the recording (2 fps), find each line's best-matching frame with a monotonic
           alignment (lines appear in script order), and score how different the two images are
  report   side-by-side sheets of the worst-matching lines (and an index HTML) for review

Usage:
  python tools/vidcompare.py capture OUT KEY [KEY ...] [--workers N]     (tools/serve.py must run)
       KEY = a story (novel.…) or album:<album entry key> for all of that entry's stories in order
  python tools/vidcompare.py align OUT VIDEO
  python tools/vidcompare.py report OUT [--top 120]
OUT is a working folder (captures, frame cache, scores). DANMEMO_URL overrides the server address.
"""
import argparse
import io
import json
import multiprocessing as mp
import os
import subprocess
import sys
import time

import numpy as np

BASE = os.environ.get("DANMEMO_URL", "http://127.0.0.1:8080/")
SW, SH = 128, 72          # alignment feature size
TALK = (11, 12, 45)       # dialogue, auto dialogue, narration
BOX = (0.70, 1.0)         # message box rows (fraction of height), masked when scoring the scene


def _capture(job):
    keys, out, wid = job
    from PIL import Image
    from playwright.sync_api import sync_playwright
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--mute-audio", "--autoplay-policy=no-user-gesture-required"])
        pg = b.new_page(viewport={"width": 1280, "height": 800})
        pg.add_init_script("localStorage.setItem('dm.settings', JSON.stringify({skipDelay: 20}))")
        for key in keys:
            pg.goto("about:blank")  # a hash change alone keeps the previous story's player around
            pg.goto(f"{BASE}#/play/{key}")
            pg.wait_for_function(f"window.__p && window.__p.novel && window.__p.novel.key === {json.dumps(key)}", timeout=20000)
            cmds = pg.evaluate("__p.novel.cmds")
            # hold the player after every typed line until the screenshot is taken
            pg.evaluate("""(() => { const p = window.__p, orig = p.typeInto.bind(p);
              p.typeInto = async (...x) => { await orig(...x); window.__hold = p.pc;
                await new Promise((r) => { window.__release = r; }); }; })()""")
            pg.evaluate("__p.setSkip(true)")
            done = set()
            while True:
                try:
                    pg.wait_for_function("window.__hold != null || !!document.querySelector('.endcard')", timeout=120000)
                except Exception:
                    print("  stuck", key, pg.evaluate("__p.pc"), flush=True)
                    break
                pc = pg.evaluate("window.__hold")
                if pc is None:
                    break
                if pc >= len(cmds) or pg.evaluate("__p.novel.key") != key:
                    print("  odd hold", key, pc, len(cmds), pg.evaluate("__p.novel.key"), flush=True)
                    pg.evaluate("window.__hold = null; window.__release()")
                    continue
                time.sleep(0.15)  # skip mode cuts fades short; let the last frame render
                png = pg.locator(".stage").screenshot()
                fn = f"{key}_{pc:04d}.jpg"
                Image.open(io.BytesIO(png)).convert("RGB").resize((640, 360)).save(os.path.join(out, "cap", fn), quality=88)
                rows.append({"key": key, "pc": pc, "file": fn, "text": str(cmds[pc][-1] if cmds[pc][0] in TALK else "")[:60]})
                done.add(pc)
                pg.evaluate("window.__hold = null; window.__release()")
            print(f"  worker {wid}: {key} {len(done)} lines", flush=True)
        b.close()
    return rows


def expand(keys):
    """album:<key> -> that album entry's stories (preview first, then the stages in order)"""
    out, album = [], None
    for k in keys:
        if not k.startswith("album:"):
            out.append(k); continue
        if album is None:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import config
            album = [e for es in json.load(open(os.path.join(config.load()["web"], "data", "album.json"))).values() for e in es]
        e = next((e for e in album if e["key"] == k[6:]), None)
        if not e:
            sys.exit(f"no album entry {k[6:]}")
        out += [s for st in e["stages"] for s in st["novels"]]
    return out


def capture(a):
    os.makedirs(os.path.join(a.out, "cap"), exist_ok=True)
    keys = expand(a.keys)
    n = max(1, min(a.workers, len(keys)))
    with mp.get_context("spawn").Pool(n) as pool:
        parts = pool.map(_capture, [(keys[i::n], a.out, i) for i in range(n)])
    by = {}
    for part in parts:
        for r in part:
            by.setdefault(r["key"], []).append(r)
    rows = [r for k in keys for r in sorted(by.get(k, []), key=lambda r: r["pc"])]
    json.dump(rows, open(os.path.join(a.out, "lines.json"), "w"), ensure_ascii=False, indent=0)
    print("captured", len(rows), "lines from", len(keys), "stories")


def _feat(img):
    """grey, small, zero-mean / unit-norm: cosine similarity by dot product"""
    v = np.asarray(img, dtype=np.float32).reshape(-1)
    v = v - v.mean()
    return v / (np.linalg.norm(v) + 1e-6)


def video_frames(video, out, fps=2):
    cache = os.path.join(out, f"frames_{fps}fps.npz")
    if os.path.exists(cache):
        return np.load(cache)["f"]
    cmd = ["ffmpeg", "-loglevel", "error", "-i", video, "-vf", f"fps={fps},scale={SW}:{SH}", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, SH, SW)
    np.savez_compressed(cache, f=fr)
    return fr


def align(a):
    from PIL import Image
    rows = json.load(open(os.path.join(a.out, "lines.json")))
    fr = video_frames(a.video, a.out)
    F = np.stack([_feat(f) for f in fr])                                     # frames × d
    L = np.stack([_feat(Image.open(os.path.join(a.out, "cap", r["file"])).convert("L").resize((SW, SH))) for r in rows])
    sim = L @ F.T                                                            # lines × frames
    n, m = sim.shape
    # monotonic: line i at frame j_i, j_i > j_{i-1}; maximise the summed similarity
    score = np.full((n, m), -1e9, np.float32)
    back = np.zeros((n, m), np.int32)
    score[0] = sim[0]
    for i in range(1, n):
        prev = score[i - 1]
        best = np.maximum.accumulate(prev)                                   # best over j' <= j
        arg = np.maximum.accumulate(np.where(prev >= best, np.arange(m), 0)) # where that best was reached
        score[i, 1:] = sim[i, 1:] + best[:-1]
        back[i, 1:] = arg[:-1]
    j = int(np.argmax(score[-1]))
    path = [0] * n
    for i in range(n - 1, -1, -1):
        path[i] = j
        j = back[i, j]
    # The alignment ignores brightness (normalised features), so it may land on a frame of the same shot
    # mid fade. Refine within the line's own span (between its neighbours) to the frame with the
    # smallest absolute difference, then score the scene with the message box masked.
    h0 = int(SH * BOX[0])
    for i, r in enumerate(rows):
        ours = np.asarray(Image.open(os.path.join(a.out, "cap", r["file"])).convert("L").resize((SW, SH)), dtype=np.float32)
        path = [int(x) for x in path] if i == 0 else path
        lo = path[i - 1] + 1 if i else max(0, path[i] - 10)
        hi = path[i + 1] if i + 1 < n else min(m, path[i] + 10)
        lo, hi = max(lo, path[i] - 20), min(max(hi, path[i] + 1), path[i] + 21)
        cand = fr[lo:hi].astype(np.float32)
        d = np.abs(cand[:, :h0] - ours[None, :h0]).mean(axis=(1, 2))
        k = lo + int(np.argmin(d))
        k = int(k); r["frame"] = k; r["t"] = round(k / 2, 1); r["sim"] = round(float(sim[i, path[i]]), 3)
        r["diff"] = round(float(d.min()), 1)
    json.dump(rows, open(os.path.join(a.out, "aligned.json"), "w"), ensure_ascii=False, indent=0)
    s = np.array([r["sim"] for r in rows])
    print(f"aligned {n} lines to {m} frames; similarity median {np.median(s):.2f}, <0.5: {(s < 0.5).sum()}")


def report(a):
    from PIL import Image, ImageDraw
    rows = json.load(open(os.path.join(a.out, "aligned.json")))
    video = json.load(open(os.path.join(a.out, "video.json")))["video"] if os.path.exists(os.path.join(a.out, "video.json")) else None
    os.makedirs(os.path.join(a.out, "pairs"), exist_ok=True)
    worst = sorted(rows, key=lambda r: -r["diff"])[: a.top]
    for r in worst:
        fn = os.path.join(a.out, "pairs", r["file"])
        if os.path.exists(fn):
            continue
        ours = Image.open(os.path.join(a.out, "cap", r["file"])).convert("RGB")
        theirs = ours
        if video:
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(r["t"]), "-i", video, "-frames:v", "1",
                                  "-vf", "scale=640:360", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
            theirs = Image.open(io.BytesIO(raw)).convert("RGB")
        im = Image.new("RGB", (1290, 384), "white")
        im.paste(theirs, (0, 24)); im.paste(ours, (650, 24))
        d = ImageDraw.Draw(im)
        d.text((4, 4), f"original {int(r['t'] // 60)}:{r['t'] % 60:04.1f}", fill="black")
        d.text((654, 4), f"player {r['key']} #{r['pc']}  diff {r['diff']}  sim {r['sim']}", fill="black")
        im.save(fn, quality=85)
    print("worst", len(worst), "->", os.path.join(a.out, "pairs"))
    for r in worst[:40]:
        print(f"{r['diff']:5.1f} {r['sim']:5.2f} {int(r['t'] // 60):3d}:{r['t'] % 60:04.1f} {r['key']} #{r['pc']} {r['text'][:30]}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("capture"); c.add_argument("out"); c.add_argument("keys", nargs="+"); c.add_argument("--workers", type=int, default=6)
    c = sp.add_parser("align"); c.add_argument("out"); c.add_argument("video")
    c = sp.add_parser("report"); c.add_argument("out"); c.add_argument("--top", type=int, default=120)
    a = ap.parse_args()
    if a.cmd == "align":
        os.makedirs(a.out, exist_ok=True)
        json.dump({"video": os.path.abspath(a.video)}, open(os.path.join(a.out, "video.json"), "w"))
    {"capture": capture, "align": align, "report": report}[a.cmd](a)


if __name__ == "__main__":
    main()
