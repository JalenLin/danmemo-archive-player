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


def collect(dirs, out):
    """First directory wins for a given file name."""
    os.makedirs(out, exist_ok=True)
    seen = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.enc"))):
            seen.setdefault(os.path.basename(f), f)
    return [(f, os.path.join(out, name[:-4] + ".json")) for name, f in sorted(seen.items())]


if __name__ == "__main__":
    cfg = config.load()
    lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else None
    src = cfg["translations"][lang] if lang else cfg
    dec = cfg["dec"] + (f"_{lang}" if lang else "")
    tasks = collect(src["novel_dirs"], f"{dec}/novel") + collect(src["master_dirs"], f"{dec}/master")
    with ProcessPoolExecutor() as ex:
        errs = [e for e in ex.map(one, tasks, chunksize=32) if e]
    print(len(tasks), "files ->", dec, ",", len(errs), "errors")
    for e in errs[:20]:
        print(e)
