"""Smoke-test the web player: play N random novels in skip mode and report command errors.

Usage: python tools/smoke.py [N] [seed]   (needs tools/serve.py running on :8080)
"""
import collections
import json
import random
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("DANMEMO_URL", "http://127.0.0.1:8080/")  # where tools/serve.py is listening

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

WEB = config.load()["web"]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
keys = list(json.load(open(f"{WEB}/data/index.json"))["titles"])
sample = random.sample(keys, n)

errors = collections.Counter()
examples = {}
timeouts = []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
    pg = b.new_page(viewport={"width": 1280, "height": 760})
    cur = {"k": None}

    def on_console(m):
        if m.type in ("warning", "error") and ("cmd failed" in m.text or "Uncaught" in m.text):
            sig = m.text[:160]
            errors[sig] += 1
            examples.setdefault(sig, cur["k"])

    pg.on("console", on_console)
    pg.on("pageerror", lambda e: on_console(type("M", (), {"type": "error", "text": "Uncaught " + str(e)})()))
    for i, k in enumerate(sample):
        cur["k"] = k
        pg.goto(f"{BASE}#/play/{k}")
        try:
            pg.wait_for_function("window.__p && window.__p.novel", timeout=10000)
            pg.evaluate("__p.setSkip(true)")
            pg.wait_for_selector(".endcard", timeout=60000)
        except Exception:
            timeouts.append((k, pg.evaluate("window.__p ? [__p.pc, __p.novel && __p.novel.cmds[__p.pc]] : null")))
        pg.goto("about:blank")
    b.close()

print(f"played {n}, timeouts {len(timeouts)}")
for t in timeouts[:10]:
    print("  timeout", t)
for sig, c in errors.most_common(20):
    print(f"{c:4d}  {sig}  e.g. {examples[sig]}")
