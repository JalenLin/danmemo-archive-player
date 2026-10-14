"""DanMemo Archive Player — one-click launcher (the packaged Windows app runs this).

Put your own game data in a `data` folder next to the program, then start it:

    DanMemoPlayer.exe                (or: python tools/launcher.py)
    data/
      com.eu.danmemo_2023-12-22.apk  the global APK (or the JP memorial app's .xapk / libapp.so), for the keys
      contents/1 ... contents/8, voice_root, single_image_root
                                     an extracted global app-data backup (the community dump)

A browser page shows what was found and builds everything into a `work` folder (keys, decrypted
data, the player's data); then the player opens. Nothing is uploaded anywhere: it is a local server.
`--step NAME` runs one build step in a child process (used internally).

The Android app runs this too (android/): it sets DANMEMO_APP (where tools/ and web/ were unpacked),
DANMEMO_HOME (for work/), DANMEMO_DATA (the data folder in shared storage) and DANMEMO_INPROCESS=1 (no child
processes there: each step runs in this process, its output captured for the page).
"""
import glob
import json
import multiprocessing
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer

FROZEN = getattr(sys, "frozen", False)
APP = (os.environ.get("DANMEMO_APP") or
       getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # bundled tools/ and web/
BASE = os.environ.get("DANMEMO_HOME") or (os.path.dirname(sys.executable) if FROZEN else os.getcwd())  # work/ (and data/)
DATA = os.environ.get("DANMEMO_DATA") or os.path.join(BASE, "data")
INPROCESS = bool(os.environ.get("DANMEMO_INPROCESS"))
WORK = os.path.join(BASE, "work")
CONFIG = os.path.join(WORK, "config.json")
SETTINGS = os.path.join(WORK, "settings.json")  # what the user picked on the setup page
KEYS = os.path.join(WORK, "keys.json")
PACK = os.path.join(BASE, "DanMemo.dmpack")  # the built player for the Android app (tools/dmpack.py)
TOOLS = os.path.join(APP, "tools")
os.environ["DANMEMO_CONFIG"] = CONFIG  # for the tools imported here as well as the steps run in child processes
os.environ["DANMEMO_KEYS"] = KEYS
sys.path.insert(0, TOOLS)


# ---------------------------------------------------------------- the user's data
def settings():
    try:
        return json.load(open(SETTINGS, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**kw):
    os.makedirs(WORK, exist_ok=True)
    s = {**settings(), **kw}
    json.dump(s, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def find_dump(path):
    """The `contents` folder of a backup the user pointed at: contents itself, its parent, or a folder a few
    levels above it (an extracted archive often adds one). Returns (folder or None, note)."""
    path = path.strip().strip('"').strip("'")
    if not path or not os.path.isdir(path):
        return None, f"Folder not found: {path}"
    for root, dirs, files in os.walk(path, followlinks=True):
        dirs[:] = [d for d in dirs if d not in ("files", "master", "voice_root", "single_image_root")]  # backup innards
        if root[len(path):].count(os.sep) > 3:
            dirs[:] = []
            continue
        if os.path.isdir(os.path.join(root, "1", "master", "divide_novel_command_enc")):
            return root, ""
        if any(f.lower().endswith(".rar") for f in files):
            return None, ("This folder has RAR parts that aren't extracted yet: open contents.part1.rar with "
                          "7-Zip or WinRAR (ZArchiver on Android), extract it, then give the extracted folder.")
    return None, "No app-data backup in this folder (expected contents/1/master/divide_novel_command_enc)."


def detect():
    """{'keysrc': path or None, 'dump': contents folder or None, 'notes': [...]}: what the user picked on the
    setup page, else what lies in data/ next to the program"""
    found = {"keysrc": None, "dump": None, "notes": []}
    st = settings()
    if st.get("apk") and os.path.exists(st["apk"]):
        found["keysrc"] = st["apk"]
    if st.get("dump"):
        found["dump"], note = find_dump(st["dump"])
        if note:
            found["notes"].append(note)
    if found["keysrc"] and found["dump"]:
        return found
    if not os.path.isdir(DATA):
        found["notes"].append(f"No data folder: create {DATA} and put the APK and the extracted backup there.")
        return found
    cands = []
    for root, dirs, files in os.walk(DATA, followlinks=True):
        if found["keysrc"] and found["dump"]:
            break
        depth = root[len(DATA):].count(os.sep)
        if depth > 4:
            dirs[:] = []
            continue
        for f in files:
            if f.lower().endswith((".apk", ".xapk")) or f == "libapp.so":
                cands.append(os.path.join(root, f))
        if os.path.isdir(os.path.join(root, "1", "master", "divide_novel_command_enc")):
            found["dump"] = found["dump"] or root
            dirs[:] = []  # don't walk the backup's ~100,000 files (slow on Android's shared storage)
    # prefer the global APK, then any other APK / xapk / libapp.so
    cands.sort(key=lambda p: (0 if "eu.danmemo" in os.path.basename(p) else 1, p))
    found["keysrc"] = found["keysrc"] or (cands[0] if cands else None)
    if not found["keysrc"]:
        found["notes"].append("Choose the APK: the global com.eu.danmemo 2023-12-22 APK, or the JP memorial app's .xapk.")
    if not found["dump"] and not st.get("dump"):
        found["notes"].append("Give the folder of the extracted app-data backup (the one with contents/1 … contents/8).")
    if not found["dump"] and glob.glob(os.path.join(DATA, "**", "*.rar"), recursive=True):
        found["notes"].append("RAR parts found but not extracted: open contents.part1.rar with 7-Zip / WinRAR "
                              "(ZArchiver on Android) and extract it into the data folder.")
    return found


def write_config(found):
    os.makedirs(os.path.join(WORK, "assets"), exist_ok=True)  # where downloads go (the first asset root)
    c = found["dump"]
    roots = [os.path.join(WORK, "assets")] + [os.path.join(c, d) for d in
             [str(i) for i in range(1, 9)] + ["voice_root", "single_image_root"] if os.path.isdir(os.path.join(c, d))]
    cfg = {
        "libapp": found["keysrc"],
        "novel_dirs": [os.path.join(c, "1", "master", "divide_novel_command_enc")],
        "master_dirs": [os.path.join(c, "1", "master", "divide_enc")],
        "asset_roots": roots,
        "dec": os.path.join(WORK, "dec"), "web": os.path.join(WORK, "web"),
        "cdn": os.path.join(WORK, "cdn"), "downloads": os.path.join(WORK, "assets"),
    }
    json.dump(cfg, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return cfg


def copy_player():
    """The player's own files (html/js/css/vendor) into work/web; work/web/data is built by build_web."""
    dst = os.path.join(WORK, "web")
    os.makedirs(dst, exist_ok=True)
    src = os.path.join(APP, "web")
    for name in os.listdir(src):
        if name in ("data", "r"):
            continue
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)


def decrypted():
    """every .enc of the configured backup already has its decrypted .json (a rebuild after a failed step)"""
    try:
        cfg = json.load(open(CONFIG, encoding="utf-8"))
    except (OSError, ValueError):
        return False
    import decrypt_all
    for kind, dirs in (("novel", cfg["novel_dirs"]), ("master", cfg["master_dirs"])):
        want = {os.path.basename(f)[:-4] for d in dirs for f in glob.glob(os.path.join(d, "*.enc"))}
        if kind == "master":
            want &= decrypt_all.PLAYER_TABLES
        have = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(cfg["dec"], kind, "*.json"))}
        if not want or not want <= have:
            return False
    return True


def built():
    return os.path.exists(os.path.join(WORK, "web", "data", "index.json"))


# ---------------------------------------------------------------- build steps (each in a child process)
STEPS = [("keys", "Derive the keys from the APK"), ("decrypt", "Decrypt the stories and master data"),
         ("fill", "Download what the backup lacks from the game's CDN (~1.6 GB, optional)"),
         ("movies", "Convert the cutscene movies (.usm -> .mp4)"),
         ("build", "Build the player's data")]
PACK_STEP = ("pack", "Pack the player for the Android app")


def ffmpeg_dir():
    """the ffmpeg shipped next to the program (Windows build), if any"""
    d = os.path.join(APP, "ffmpeg")
    return d if os.path.isdir(d) else None


def have_ffmpeg():
    import usm
    if ffmpeg_dir():
        return True
    return usm.have_ffmpeg()


def run_step(name):
    """Inside the child: run one tool as if from the command line."""
    os.environ["DANMEMO_CONFIG"] = CONFIG
    os.environ["DANMEMO_KEYS"] = KEYS
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    if name == "keys":
        import keys
        sample = (glob.glob(os.path.join(cfg["novel_dirs"][0], "*.enc")) or [None])[0]
        sys.argv = ["keys.py", cfg["libapp"]] + ([sample] if sample else [])
        return keys.main()
    if name == "decrypt":
        import decrypt_all
        return decrypt_all.main(["decrypt_all.py", "--player"])
    if name == "pack":
        import dmpack
        return dmpack.main(["dmpack.py", PACK])
    if name == "movies":
        import usm
        if not usm.have_ffmpeg():
            print("ffmpeg not found: the cutscene movies are left out", flush=True)
            return 0
        done, failed = usm.convert_missing(cfg["asset_roots"], cfg["downloads"])
        print(f"converted movies: {done}" + (f", failed: {len(failed)}" if failed else ""), flush=True)
        return 0
    import runpy
    mod = {"fill": "fill_gaps", "build": "build_web"}[name]
    sys.argv = [mod + ".py"]
    runpy.run_module(mod, run_name="__main__")
    return 0


class Job:
    def __init__(self):
        self.log, self.state, self.step, self.lock = [], "idle", None, threading.Lock()

    def say(self, line):
        with self.lock:
            self.log.append(line.rstrip("\n"))
            del self.log[:-400]
        if sys.__stdout__:  # the console (or Android's logcat); steps run in-process print into the log instead
            print(line.rstrip("\n"), file=sys.__stdout__, flush=True)

    def start(self, download, pack=False):
        if self.state == "running":
            return
        self.state = "running"
        threading.Thread(target=self._run, args=(download, pack), daemon=True).start()

    def _run(self, download, pack=False):
        try:
            if pack:  # only the pack, of the player as built
                if not built():
                    self.state = "error"
                    return
            else:
                found = detect()
                if not (found["keysrc"] and found["dump"]):
                    for n in found["notes"]:
                        self.say("! " + n)
                    self.state = "error"
                    return
                write_config(found)
                copy_player()
            for name, title in [PACK_STEP] if pack else STEPS:
                if name == "fill" and not download:
                    continue
                if name == "keys" and os.path.exists(KEYS):
                    continue
                if name == "decrypt" and decrypted():
                    self.say("== Decrypted data already complete, skipped")
                    continue
                self.step = title
                self.say(f"== {title}")
                if INPROCESS:
                    code = self._inprocess(name)
                    if code:
                        self.say(f"! step failed: {title} (exit {code})")
                        self.state = "error"
                        return
                    continue
                cmd = ([sys.executable] if FROZEN else [sys.executable, os.path.abspath(__file__)]) + ["--step", name]
                env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
                ff = os.path.join(APP, "ffmpeg")
                if os.path.isdir(ff):
                    env["PATH"] = ff + os.pathsep + env.get("PATH", "")
                p = subprocess.Popen(cmd, cwd=BASE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace",
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                for line in p.stdout:
                    self.say(line)
                if p.wait() != 0:
                    self.say(f"! step failed: {title} (exit {p.returncode})")
                    self.state = "error"
                    return
            self.step = None
            self.state = "done"
            self.say("== Done." if pack else "== Done. Open the player.")
        except Exception as e:  # keep the page informative instead of dying silently
            self.say(f"! {type(e).__name__}: {e}")
            self.state = "error"


    def _inprocess(self, name):
        """Run a step here (Android), its prints going to the log. Returns the exit code."""
        import contextlib
        import traceback

        job = self

        class Lines:
            def __init__(self):
                self.buf = ""

            def write(self, s):
                self.buf += s
                *done, self.buf = self.buf.split("\n")
                for line in done:
                    job.say(line)
                return len(s)

            def flush(self):
                pass

        out = Lines()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = run_step(name)
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except Exception:
            for line in traceback.format_exc().splitlines():
                self.say(line)
            code = 1
        if out.buf:
            self.say(out.buf)
        return code or 0


JOB = Job()


# ---------------------------------------------------------------- the local server
def make_handler():
    import serve

    class Handler(serve.Handler):
        web = os.path.join(WORK, "web")
        roots = json.load(open(CONFIG, encoding="utf-8"))["asset_roots"] if os.path.exists(CONFIG) else []

        def do_GET(self):
            if self.path in ("/setup", "/setup/"):
                return self._send(200, "text/html; charset=utf-8", open(os.path.join(TOOLS, "launcher.html"), "rb").read())
            if self.path.startswith("/setup/status"):
                found = detect()
                body = {"found": {"keysrc": found["keysrc"], "dump": found["dump"], "notes": found["notes"]},
                        "data": DATA, "state": JOB.state, "step": JOB.step, "built": built(), "log": JOB.log[-200:],
                        "ffmpeg": have_ffmpeg(), "pack": PACK if os.path.exists(PACK) else None}
                return self._send(200, "application/json", json.dumps(body, ensure_ascii=False).encode())
            if not built() and self.path in ("/", "/index.html"):
                self.send_response(302); self.send_header("Location", "/setup"); self.end_headers()
                return
            # pick up the asset roots written by a build that just finished
            if os.path.exists(CONFIG):
                type(self).roots = json.load(open(CONFIG, encoding="utf-8"))["asset_roots"]
            return super().do_GET()

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            if self.path.startswith("/setup/apk"):  # the APK chosen on the page, streamed as the request body
                from urllib.parse import unquote
                name = os.path.basename(unquote(self.headers.get("X-File-Name") or "app.apk")) or "app.apk"
                if not name.lower().endswith((".apk", ".xapk", ".so")):
                    return self._send(400, "application/json", b'{"error":"not an APK"}')
                os.makedirs(os.path.join(WORK, "apk"), exist_ok=True)
                dst = os.path.join(WORK, "apk", name)
                with open(dst + ".part", "wb") as f:
                    left = n
                    while left > 0:
                        buf = self.rfile.read(min(1 << 20, left))
                        if not buf:
                            break
                        f.write(buf); left -= len(buf)
                os.replace(dst + ".part", dst)
                save_settings(apk=dst)
                if os.path.exists(KEYS):
                    os.remove(KEYS)  # derive again from the new APK
                return self._send(200, "application/json", b'{"ok":true}')
            if self.path.startswith("/setup/dump"):
                path = json.loads(self.rfile.read(n) or b"{}").get("path", "")
                folder, note = find_dump(path)
                if folder:
                    save_settings(dump=folder)
                body = json.dumps({"ok": bool(folder), "folder": folder, "note": note}, ensure_ascii=False).encode()
                return self._send(200, "application/json", body)
            if self.path.startswith("/setup/build"):
                opts = json.loads(self.rfile.read(n) or b"{}")
                JOB.start(bool(opts.get("download")))
                return self._send(200, "application/json", b'{"ok":true}')
            if self.path.startswith("/setup/pack"):
                JOB.start(False, pack=True)
                return self._send(200, "application/json", b'{"ok":true}')
            self.send_error(404)

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def free_port(start=8080):
    for p in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 0


def main():
    multiprocessing.freeze_support()
    if "--step" in sys.argv:
        sys.exit(run_step(sys.argv[sys.argv.index("--step") + 1]) or 0)
    os.makedirs(os.path.join(WORK, "web"), exist_ok=True)
    copy_player()
    port = int(os.environ.get("DANMEMO_PORT") or free_port())
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler())
    url = f"http://127.0.0.1:{port}/" + ("" if built() else "setup")
    print(f"DanMemo Archive Player: {url}\n(data: {DATA}  work: {WORK})\nClose this window to stop.", flush=True)
    if not os.environ.get("DANMEMO_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
