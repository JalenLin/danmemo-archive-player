"""Project configuration: where the user's own game data lives.

Reads config.json at the project root (copy config.example.json and edit). Relative paths are
resolved against the project root. Nothing in here ships game data; it only points at it.
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _abs(p):
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(ROOT, p))


def load():
    path = os.environ.get("DANMEMO_CONFIG") or os.path.join(ROOT, "config.json")  # env var: use another config
    if not os.path.exists(path):
        raise SystemExit("config.json not found: copy config.example.json to config.json and edit the paths.")
    cfg = json.load(open(path, encoding="utf-8"))
    cfg["libapp"] = _abs(cfg["libapp"])
    for k in ("novel_dirs", "master_dirs", "asset_roots"):
        cfg[k] = [_abs(p) for p in cfg.get(k, [])]
    for lang, t in cfg.get("translations", {}).items():
        for k in ("novel_dirs", "master_dirs"):
            t[k] = [_abs(p) for p in t.get(k, [])]
    cfg["dec"] = _abs(cfg.get("dec", "dec"))
    cfg["web"] = _abs(cfg.get("web", "web"))
    return cfg
