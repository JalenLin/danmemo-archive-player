"""Play stories through the web player in skip mode and report what goes wrong.

Every command runs and every asset loads; only waits are skipped (one short pause per line), so a
story takes seconds instead of minutes. Reports stories that never reach their end (timeouts),
commands that throw, page errors and assets the server can't deliver (HTTP 4xx/5xx).

Usage: python tools/smoke.py [N|all] [seed] [--workers W] [--skip-delay MS] [--report out.json]
  (needs tools/serve.py running; DANMEMO_URL overrides http://127.0.0.1:8080/; SMOKE_STORAGE sets more
  localStorage, e.g. '{"dm.subs": {"main": "en", "sub": "ja"}}' for two-language subtitles)
"""
import argparse
import collections
import json
import multiprocessing as mp
import os
import random
import sys
import time

BASE = os.environ.get("DANMEMO_URL", "http://127.0.0.1:8080/")  # where tools/serve.py is listening

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config


def run(job):
    keys, skip_delay, wid = job
    from playwright.sync_api import sync_playwright
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        ctx = b.new_context(viewport={"width": 1280, "height": 760})
        ctx.add_init_script(f"localStorage.setItem('dm.settings', JSON.stringify({{skipDelay: {skip_delay}}}))")
        # SMOKE_STORAGE='{"dm.subs": {"main": "en", "sub": "ja"}}': more of the viewer's settings
        for k, v in json.loads(os.environ.get("SMOKE_STORAGE") or "{}").items():
            ctx.add_init_script(f"localStorage.setItem({json.dumps(k)}, {json.dumps(json.dumps(v))})")
        pg = ctx.new_page()
        cur = {"r": None}

        def on_console(m):
            if cur["r"] is not None and m.type in ("warning", "error") and ("cmd failed" in m.text or "Uncaught" in m.text):
                cur["r"]["errors"].append(m.text[:200])

        pg.on("console", on_console)
        pg.on("pageerror", lambda e: cur["r"] is not None and cur["r"]["errors"].append("Uncaught " + str(e)[:200]))
        # setup/status: the page asks whether a setup page is there (only the Windows / Android app has one)
        pg.on("response", lambda r: cur["r"] is not None and r.status >= 400 and not r.url.endswith("/setup/status")
              and cur["r"]["http"].append(f"{r.status} {r.url.split('/', 3)[-1]}"))
        for i, k in enumerate(keys):
            r = cur["r"] = {"key": k, "errors": [], "http": [], "timeout": None, "sec": 0}
            t0 = time.time()
            try:
                pg.goto(f"{BASE}#/play/{k}")
                pg.wait_for_function("window.__p && window.__p.novel", timeout=20000)
                n = pg.evaluate("__p.novel.cmds.length")
                # the stage must fill the player (a CSS slip once left it a strip behind the toolbar)
                box = pg.evaluate("(() => { const r = document.querySelector('.stage').getBoundingClientRect(); return [r.width, r.height]; })()")
                if box[0] < 600 or box[1] < 300:
                    r["errors"].append(f"layout: stage {box[0]:.0f}x{box[1]:.0f}")
                pg.evaluate("__p.setSkip(true)")
                pg.wait_for_selector(".endcard", timeout=int(60000 + n * 60))
            except Exception as e:
                try:
                    r["timeout"] = pg.evaluate("window.__p && window.__p.novel ? [__p.pc, __p.novel.cmds[__p.pc]] : null")
                except Exception:
                    r["timeout"] = str(e)[:120]
                r["timeout"] = r["timeout"] or "never loaded"
            r["sec"] = round(time.time() - t0, 1)
            cur["r"] = None
            pg.goto("about:blank")
            out.append(r)
            if (i + 1) % 200 == 0:
                print(f"  worker {wid}: {i + 1}/{len(keys)}", flush=True)
        b.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", nargs="?", default="100")
    ap.add_argument("seed", nargs="?", type=int, default=1)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--skip-delay", type=int, default=20, help="ms per line while skipping")
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    keys = sorted(json.load(open(f"{config.load()['web']}/data/index.json"))["titles"])
    if a.n != "all":
        random.seed(a.seed)
        keys = random.sample(keys, int(a.n))
    chunks = [keys[i::a.workers] for i in range(a.workers)]
    t0 = time.time()
    with mp.get_context("spawn").Pool(a.workers) as pool:
        res = [r for part in pool.map(run, [(c, a.skip_delay, i) for i, c in enumerate(chunks)]) for r in part]
    bad = [r for r in res if r["timeout"] or r["errors"] or r["http"]]
    print(f"played {len(res)} in {(time.time() - t0) / 60:.1f} min: timeouts {sum(1 for r in res if r['timeout'])}, "
          f"with command/page errors {sum(1 for r in res if r['errors'])}, with failed asset loads {sum(1 for r in res if r['http'])}")
    sig = collections.Counter(e.split(" ", 1)[0] + " " + (e.split(" ", 2)[1][:60] if " " in e else "") for r in res for e in r["errors"])
    for s, c in sig.most_common(15):
        print(f"{c:5d}  {s}")
    http = collections.Counter(h for r in res for h in r["http"])
    for h, c in http.most_common(10):
        print(f"{c:5d}  {h}")
    for r in [r for r in res if r["timeout"]][:10]:
        print("  timeout", r["key"], r["timeout"])
    if a.report:
        json.dump({"played": len(res), "problems": bad}, open(a.report, "w"), ensure_ascii=False, indent=1)
        print("report:", a.report)


if __name__ == "__main__":
    main()
