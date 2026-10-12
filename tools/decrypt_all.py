"""Decrypt all novel commands and master data listed in config.json to JSON.

Usage: python tools/decrypt_all.py [--lang en]
  default      -> <dec>/novel, <dec>/master
  --lang XX    -> <dec>_XX/novel, <dec>_XX/master   (from config "translations")
"""
import glob
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

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
    workers = min(os.cpu_count() or 1, 61)  # 61: ProcessPoolExecutor's limit on Windows
    print(f"decrypting {len(tasks)} files with {workers} processes", flush=True)
    import time
    errs, done, last = [], 0, time.time()
    with ProcessPoolExecutor(workers) as ex:
        futs = [ex.submit(one, t) for t in tasks]
        from concurrent.futures import as_completed
        for f in as_completed(futs):
            done += 1
            e = f.result()
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
