"""Screenshot helper for testing the web player: python tools/shot.py <hash> <out.png> [clicks] [wait_s]"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.environ.get("DANMEMO_URL", "http://127.0.0.1:8080/")  # where tools/serve.py is listening

url = BASE + sys.argv[1]
out = sys.argv[2]
clicks = int(sys.argv[3]) if len(sys.argv) > 3 else 0
wait = float(sys.argv[4]) if len(sys.argv) > 4 else 2

with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 1280, "height": 760})
    logs = []
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
    pg.goto(url)
    time.sleep(wait)
    for _ in range(clicks):
        pg.mouse.click(640, 400)
        time.sleep(0.8)
    time.sleep(1)
    pg.screenshot(path=out)
    for l in logs[-15:]:
        print(l)
    b.close()
