"""Decrypt all novel commands and master data listed in config.json to JSON.

Usage: python tools/decrypt_all.py [--lang en]
  default      -> <dec>/novel, <dec>/master
  --lang XX    -> <dec>_XX/novel, <dec>_XX/master   (from config "translations")
"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import fbdump


def one(args):
    src, dst = args
    try:
        _, d = fbdump.load(src)
        json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False)
        return None
    except Exception as e:
        return f"{src}: {e!r}"


# master tables the player build reads (build_web.py, fill_gaps.py, cardstat.py); --player decrypts only these.
# The others (enemies, quests, shop …) aren't needed, and a few are slow: enemy.enc alone takes ~100 s.
PLAYER_TABLES = {"adventure", "adventureEncounter", "adventureEpisode", "adventureStage", "alarmVoice", "battleEffect",
                 "bgm", "character", "characterCostume", "characterPresentCharacterInfo", "characterPresentInfo",
                 "heroSublimateLevelStep", "movieUsm", "novel", "novelPortrait", "pc", "pcAbility", "pcAbilityPanel",
                 "pcAffiliation", "pcGuest", "pcGuestLevelStep", "pcJob", "pcLevelStep", "pcSkill", "scenarioLwf", "se",
                 "singleImage", "startNovel", "voice"}


def collect(dirs, out):
    """First directory wins for a given file name."""
    os.makedirs(out, exist_ok=True)
    seen = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.enc"))):
            seen.setdefault(os.path.basename(f), f)
    return [(f, os.path.join(out, name[:-4] + ".json")) for name, f in sorted(seen.items())]


def run(tasks):
    """Decrypt the tasks in parallel, yielding each one's error (or None) as it finishes. A process pool where
    Python has one; on Android (no working multiprocessing: no sem_open) forked workers that each take every
    n-th task and report through a pipe; one at a time if even that fails. DANMEMO_POOL=fork / serial forces one."""
    mode = os.environ.get("DANMEMO_POOL") or ("fork" if hasattr(sys, "getandroidapilevel") else "pool")
    if mode == "pool":
        from concurrent.futures import ProcessPoolExecutor, as_completed  # imports _multiprocessing: not on Android
        workers = min(os.cpu_count() or 1, 61)  # 61: ProcessPoolExecutor's limit on Windows
        print(f"decrypting {len(tasks)} files with {workers} processes", flush=True)
        with ProcessPoolExecutor(workers) as ex:
            for f in as_completed([ex.submit(one, t) for t in tasks]):
                yield f.result()
        return
    if mode == "fork" and hasattr(os, "fork"):
        # phones: a handful of workers (each holds a big table in memory at the start: biggest files go first)
        workers = max(1, min(os.cpu_count() or 1, int(os.environ.get("DANMEMO_WORKERS") or 4)))
        try:
            yield from fork_run(tasks, workers)
            return
        except OSError as e:
            print(f"parallel decryption unavailable ({e}); one file at a time", flush=True)
    print(f"decrypting {len(tasks)} files one at a time", flush=True)
    for t in tasks:
        yield one(t)


def fork_run(tasks, workers):
    print(f"decrypting {len(tasks)} files with {workers} worker processes", flush=True)
    r, w = os.pipe()
    pids = []
    try:
        for i in range(workers):
            pid = os.fork()
            if pid == 0:  # child: never return into the caller (or, on Android, into the app)
                code = 0
                try:
                    os.close(r)
                    for t in tasks[i::workers]:
                        e = one(t)
                        # one line per finished file, under PIPE_BUF so lines from different workers don't mix
                        os.write(w, ((e or "").replace("\n", " ")[:1000] + "\n").encode("utf-8", "replace"))
                except BaseException:
                    code = 1
                finally:
                    os._exit(code)
            pids.append(pid)
    finally:
        os.close(w)
    with os.fdopen(r, "rb") as f:
        got = 0
        for line in f:
            got += 1
            yield line.decode("utf-8", "replace").rstrip("\n") or None
    for pid in pids:
        os.waitpid(pid, 0)
    if got < len(tasks):  # a worker died (out of memory?): do what it left, here
        print(f"{len(tasks) - got} files left by a stopped worker; decrypting them here", flush=True)
        for t in tasks:
            if not os.path.exists(t[1]):
                yield one(t)


def main(argv=None):
    argv = sys.argv if argv is None else argv
    cfg = config.load()
    lang = argv[argv.index("--lang") + 1] if "--lang" in argv else None
    src = cfg["translations"][lang] if lang else cfg
    dec = cfg["dec"] + (f"_{lang}" if lang else "")
    masters = collect(src["master_dirs"], f"{dec}/master")
    if "--player" in argv:
        masters = [t for t in masters if os.path.basename(t[0])[:-4] in PLAYER_TABLES]
    tasks = collect(src["novel_dirs"], f"{dec}/novel") + masters
    # biggest first, one at a time: a few huge master tables (tens of thousands of strings each) left for the
    # end used to keep two or three cores busy for minutes while the rest sat idle
    tasks.sort(key=lambda t: -os.path.getsize(t[0]))
    errs, done, last = [], 0, time.time()
    for e in run(tasks):
        done += 1
        if e:
            errs.append(e)
        if time.time() - last > 3 or done == len(tasks):
            print(f"  {done}/{len(tasks)}", flush=True)
            last = time.time()
    print(len(tasks), "files ->", dec, ",", len(errs), "errors")
    for e in errs[:20]:
        print(e)
    return 1 if errs and len(errs) == len(tasks) else 0


if __name__ == "__main__":
    sys.exit(main())
