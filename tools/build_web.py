"""Build web/data from decrypted master + novel JSON (dec/) and downloaded assets.

Outputs
  web/data/index.json            story tree: category > adventure > episode > stage > novel keys
  web/data/others.json           novels not reachable from the story tree, grouped by key prefix
  web/data/novel/<key>.json      {key, title, cmds:[[type, arg3..]], res:{assetKey: resolved}}
Asset roots come from config.json ("asset_roots"); each is exposed to the browser as web/r/<i>
(a symlink created here), so web paths look like r/0/files/...
"""
import collections
import glob
import hashlib
import json
import subprocess
import os
import re

from PIL import Image

import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

CFG = config.load()
DEC = CFG["dec"]
WEB = CFG["web"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def link_roots():
    """web/r/<i> -> asset root i; returns [(web_prefix, disk_prefix)]."""
    rdir = os.path.join(WEB, "r")
    os.makedirs(rdir, exist_ok=True)
    for old in os.listdir(rdir):
        if os.path.islink(os.path.join(rdir, old)):
            os.unlink(os.path.join(rdir, old))
    roots = []
    for i, disk in enumerate(CFG["asset_roots"]):
        if not os.path.isdir(disk):
            print("asset root missing, skipped:", disk)
            continue
        os.symlink(disk, os.path.join(rdir, str(i)))
        roots.append((f"r/{i}/", disk.rstrip("/") + "/"))
    return roots


ROOTS = link_roots()
VOICE = {}
GACHA_VOICE_ALIAS = {}


def gacha_voice(f75):
    """Resolve a card's gacha-hit voice (pc field 75) to a served path: the dedicated recording if
    present, else the aliased story voice it points to (per gacha_voice_alias.json)."""
    if not f75:
        return None
    direct = VOICE.get("voice_" + f75.split(".", 1)[1])
    return direct or VOICE.get(GACHA_VOICE_ALIAS.get(f75, ""))

# Event list cells the offline app doesn't ship (it has only the album's 48) exist solely in the global
# app's CDN set; most are localised, but these early ones reuse the Japanese artwork (checked by eye).
JP_TEXT_CELLS = {
    7090000101, 7090000102, 7090000201, 7090000301, 7090000401, 7090000501, 7090000601, 7090000701,
    7090000901, 7090001001, 7090001101, 7090001201, 7090001401, 7090010101,
    7090020101, 7090030101, 7090040101, 7090050101, 7090060101, 7090070101, 7090080101, 7090090101,
    7090100101, 7090110101, 7090120201, 7090120202, 7090120203, 7090120204,
}

# The memorial app's album picks 48 of the original events (adventureEpisode f29 = section, f30 = order).
# Other app data (e.g. the global client's) has the same episodes but not this selection; use it then.
ALBUM_DEFAULT = {
    7160000101: (1, 100), 7160000201: (1, 99), 7160000301: (1, 97), 7160000401: (1, 95), 7160000501: (1, 92),
    7160000601: (1, 89), 7160000701: (1, 87), 7160000801: (1, 84), 7160000901: (1, 82), 7160001301: (1, 81),
    7160001401: (1, 79), 7160001501: (1, 77), 7160001901: (1, 76), 7160002001: (1, 74), 7160002101: (1, 72),
    7090120226: (2, 49), 7090120210: (2, 48), 7090003701: (2, 47), 7090120218: (2, 46), 7090005101: (2, 45),
    7090005201: (2, 44), 7090120219: (2, 43), 7090006801: (2, 42), 7090010701: (2, 41), 7090010801: (2, 40),
    7090009301: (2, 39), 7090009401: (2, 38), 7090002701: (2, 37), 7090007901: (2, 36), 7090009101: (2, 35),
    7090002001: (2, 34), 7090008501: (2, 33), 7090007301: (2, 32), 7090007501: (2, 31), 7090000801: (2, 30),
    7090004301: (2, 29), 7090010901: (2, 28), 7090004001: (2, 27), 7160001001: (2, 26), 7090010301: (2, 25),
    7090009701: (2, 24), 7090009801: (2, 23), 7090011001: (2, 22), 7090011401: (2, 21), 7090120231: (2, 20),
    7090120215: (2, 12), 7090120223: (2, 11), 7090120225: (2, 10),
}

CATEGORY = {1: "メイン", 2: "キャラクエ", 3: "ふれあい", 4: "衣装", 5: "曜日イベント", 6: "経験値クエスト",
            7: "ヴァリスクエスト", 8: "降臨イベント", 9: "ストーリーイベント", 10: "チュートリアル",
            11: "エイナの学習クエスト", 12: "怪物祭", 13: "迷宮踏破", 14: "復帰応援クエスト", 15: "栄光挑戦",
            16: "マップイベント", 17: "レイドイベント", 18: "武器素材クエスト", 19: "ファミリア共闘", 20: "派閥闘劇",
            21: "冒険者レベル", 22: "派閥殲滅戦", 23: "デイリーリセットクエスト", 24: "英雄昇華チュートリアル",
            25: "ウィークリークエスト", 26: "七闘領域", 27: "決戦試練", 28: "派閥大戦"}
# 2=キャラクエ, 3=ふれあい, 4=衣装 are shown under the per-character view (characters.json), not the main tree
HIDDEN_CATEGORIES = {2, 3, 4}


def s32(x):
    return ((x & 0xFFFFFFFF) ^ 0x80000000) - 0x80000000


def table(name):
    return json.load(open(f"{DEC}/master/{name}.json"))["0"]


def find(rel):
    """Resolve a path relative to an asset root ('files/...') to a web path, or None."""
    for web, disk in ROOTS:
        if os.path.exists(disk + rel):
            return web + rel
    return None


def jp_md5s():
    """md5s of Japanese-original files: the memorial app's manifests + old JP online builds'
    (cdn/legacy/, tools/legacy_manifests.py). Used to tell a JP list cell from a global (English) one."""
    out = set()
    for f in glob.glob(os.path.join(ROOT, "cdn", "project.manifest*")) + glob.glob(os.path.join(ROOT, "cdn", "legacy", "*", "*.manifest*")):
        try:
            out.update(v["md5"] for v in json.load(open(f))["assets"].values())
        except (OSError, ValueError, KeyError):
            pass
    return out


def is_jp_file(rel, md5s):
    for _, disk in ROOTS:
        if os.path.exists(disk + rel):
            return hashlib.md5(open(disk + rel, "rb").read()).hexdigest() in md5s
    return False


def index_dir(rel_dirs, ext):
    """basename (without ext) -> web path, scanning asset roots (first root wins)."""
    idx = {}
    for web, disk in ROOTS:
        for rd in rel_dirs:
            base = disk + rd
            for dp, _, fs in os.walk(base):
                for f in fs:
                    if f.endswith(ext):
                        idx.setdefault(f[: -len(ext)], web + os.path.relpath(os.path.join(dp, f), disk))
    return idx


def portrait_info(dirname):
    for web, disk in ROOTS:
        d = f"{disk}files/character/novel_portrait/{dirname}"
        if os.path.isdir(d):
            faces, body, cut = [], False, None
            for f in os.listdir(d):
                if f.endswith(".png"):
                    # "<dir>.<face>.png", or a lone "<dir>.png" (face "")
                    part = "" if f == dirname + ".png" else f[len(dirname) + 1 : -4]
                    if part == "body":
                        body = True
                    else:
                        faces.append(part)
                elif f.endswith("cutout.plist"):
                    m = re.search(r"cutout_coordinate</key>\s*<string>\{(-?\d+),(-?\d+)\}", open(os.path.join(d, f)).read())
                    if m:
                        cut = [int(m.group(1)), int(m.group(2))]
            faces.sort()
            size = lambda part: list(Image.open(f"{d}/{dirname}{'.' + part if part else ''}.png").size)
            info = {"base": f"{web}files/character/novel_portrait/{dirname}/{dirname}", "faces": faces,
                    "body": body, "cut": cut}
            if faces:
                info["fs"] = size("normal" if "normal" in faces else faces[0])  # face (or full) image size
            if body:
                info["bs"] = size("body")
            return info
    return None

MOVIE_GROUPS = [("6th_movie_", "6周年ムービー")]  # file-name prefix -> section title (others: "ムービー")


def build_movies(refs, movie, titles):
    """data/movies.json: the cutscene movies the stories play, each with the stories it appears in, in story
    order, plus a poster frame (needs ffmpeg; skipped otherwise)."""
    os.makedirs(f"{WEB}/data/movies", exist_ok=True)
    groups = collections.OrderedDict()
    for k, nl in sorted(refs.items(), key=lambda kv: (min(n for n, _ in kv[1]), kv[0])):
        name = movie.get(k)
        src = name and find(f"files/movie/{name}.mp4")
        if not src:
            continue
        disk = os.path.join(WEB, src)
        poster, dur = None, None
        try:
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", disk],
                                       capture_output=True, text=True, timeout=60).stdout.strip() or 0) or None
            out = f"{WEB}/data/movies/{name}.jpg"
            if not os.path.exists(out):
                # try a few frames and keep the busiest one (cutscenes often flash to white/black)
                best = None
                for i, frac in enumerate((0.2, 0.35, 0.5, 0.65, 0.8)):
                    tmp = f"{out}.{i}.jpg"
                    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(round((dur or 4) * frac, 2)), "-i", disk,
                                    "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", tmp], timeout=120)
                    if os.path.exists(tmp):
                        from PIL import Image, ImageStat
                        score = sum(ImageStat.Stat(Image.open(tmp).convert("L")).stddev)
                        if best is None or score > best[0]:
                            best = (score, tmp)
                for i in range(5):
                    tmp = f"{out}.{i}.jpg"
                    if best and tmp == best[1]:
                        os.replace(tmp, out)
                    elif os.path.exists(tmp):
                        os.remove(tmp)
            if os.path.exists(out):
                poster = f"data/movies/{name}.jpg"
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        title = next((t for p, t in MOVIE_GROUPS if name.startswith(p)), "ムービー")
        groups.setdefault(title, []).append({"name": name, "src": src, "poster": poster,
                                             "duration": round(dur, 1) if dur else None,
                                             "novels": [{"key": nk, "title": titles.get(nk, nk)} for _, nk in sorted(nl)]})
    json.dump([{"title": t, "items": v} for t, v in groups.items()], open(f"{WEB}/data/movies.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("movies", {t: len(v) for t, v in groups.items()})


def main():
    os.makedirs(f"{WEB}/data/novel", exist_ok=True)

    novel = {r["0"]: r for r in table("novel")}
    single = {r["2"]: r["0"] for r in table("singleImage")}
    bgm = {r["1"]: r["2"] for r in table("bgm")}
    se = {r["1"]: r["2"] for r in table("se")}
    lwf = {r["1"]: r["0"] for r in table("scenarioLwf")}
    battle = {r["5"]: r["0"] for r in table("battleEffect") if r.get("5")}
    movie = {r["1"]: r["2"] for r in table("movieUsm")}
    portrait = {r["1"]: r["2"] for r in table("novelPortrait")}

    snd = index_dir(["files/sound/bgm", "files/sound/se"], ".ogg")
    img = index_dir(["files/ui/single_image"], ".jpg")
    voice = index_dir(["files/sound/voice", "files/sound/voice_common", "files/sound/voice_episode"], ".ogg")
    global VOICE, GACHA_VOICE_ALIAS
    VOICE = voice
    # Some gacha-hit voices are aliases to a real (story) voice file; map built from the global
    # backup's voice table (tools/gacha_voice_alias.json). Optional — absent is fine.
    try:
        GACHA_VOICE_ALIAS = json.load(open(os.path.join(os.path.dirname(__file__), "gacha_voice_alias.json"), encoding="utf-8"))
    except Exception:
        GACHA_VOICE_ALIAS = {}
    print("sound files", len(snd), "voice files", len(voice), "gacha voice aliases", len(GACHA_VOICE_ALIAS))

    pinfo_cache = {}

    def resolve(key):
        kind, _, name = key.partition(".")
        if kind == "single_image" and key in single:
            return img.get(str(single[key]))
        if kind == "novel_portrait" and key in portrait:
            d = portrait[key]
            if d not in pinfo_cache:
                pinfo_cache[d] = portrait_info(d)
            return pinfo_cache[d]
        if kind == "bgm" and key in bgm:
            return snd.get(bgm[key].split("/")[-1])
        if kind == "se" and key in se:
            return snd.get(se[key].split("/")[-1])
        if kind == "voice":
            return voice.get("voice_" + name)
        if kind == "scenario_lwf" and key in lwf:
            i = lwf[key]
            return find(f"files/lwf/scenarioLwf/{i}/{i}.lwf")
        if kind == "battle_effect" and key in battle:
            i = battle[key]
            return find(f"files/lwf/battleLwf/{i}/{i}.lwf")
        if kind == "movie_usm" and key in movie:
            return find(f"files/movie/{movie[key]}.mp4") or find(f"files/movie/{movie[key]}.usm")
        return None

    # ---- novels
    keyre = re.compile(r"^(single_image|novel_portrait|bgm|se|voice|scenario_lwf|battle_effect|movie_usm)\.[\w.\-]+$")
    novels = {}
    movie_refs = collections.defaultdict(list)  # movie_usm key -> [(novel id, novel key)] for the movie page
    lines = {}  # novel key -> its dialogue, to recognise rerun copies
    missing = collections.Counter()
    for f in sorted(glob.glob(f"{DEC}/novel/*.json")):
        cmds = json.load(open(f))["0"]
        nid = cmds[0]["1"]
        row = novel.get(nid) or novel.get(s32(nid))
        key, title = row["1"], row.get("2", "")
        out, res = [], {}
        for c in cmds:
            args = [str(c.get(str(i), "")) for i in range(3, 10)]
            while args and args[-1] == "":
                args.pop()
            out.append([c["2"]] + args)
            for a in args:
                for tok in re.split(r"[\s,]+", a):
                    if tok.startswith("movie_usm.") and (nid, key) not in movie_refs[tok]:
                        movie_refs[tok].append((nid, key))
                    if keyre.match(tok) and tok not in res:
                        r = resolve(tok)
                        res[tok] = r
                        if r is None:
                            missing[tok.split(".")[0]] += 1
        json.dump({"key": key, "title": title, "cmds": out, "res": res},
                  open(f"{WEB}/data/novel/{key}.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        novels[key] = title
        lines[key] = tuple(c[-1] for c in out if c[0] in (11, 12, 45) and len(c) > 1)
    print("novels", len(novels), "unresolved asset refs", dict(missing))

    # ---- story tree
    adv = table("adventure")
    eps = collections.defaultdict(list)
    for r in table("adventureEpisode"):
        eps[r.get("2")].append(r)
    stages = collections.defaultdict(list)
    for r in table("adventureStage"):
        stages[r.get("1")].append(r)
    enc = collections.defaultdict(list)
    for r in table("adventureEncounter"):
        enc[r.get("1")].append(r)

    used = set()
    stage_novels = {}  # adventureStage id -> [novel keys] (also used for costume stories on cards)
    cats = collections.OrderedDict()
    char_story = collections.defaultdict(dict)  # char code -> {"quest": ad, "fureai": ad}
    ep_by_id = {}  # adventureEpisode id -> ep dict (for the album)
    # the JP memorial app's data marks its album (f29); other app data (e.g. global) has its own,
    # localised list cells for every event, so show them all there
    memorial = any(r.get("29") for r in table("adventureEpisode"))
    jp = jp_md5s() if memorial else set()
    for a in adv:
        cat = a.get("2")
        ad = {"title": a.get("4", "").strip(), "key": a["1"], "episodes": []}
        for e in eps.get(a["0"], []):
            ep = ep_by_id[e["0"]] = {"title": e.get("4", "").strip(), "sub": e.get("5", "").strip(), "stages": []}
            if e.get("6") and e.get("7"):  # 開催期間 (unix time)
                ep["start"], ep["end"] = e["6"], e["7"]
            rel = f"files/adventure/episode_list_cell/{e['0']}.png"
            if not memorial or e["0"] in JP_TEXT_CELLS or is_jp_file(rel, jp):
                cell = find(rel)
                if cell:
                    ep["banner"] = cell
            seen = set()  # each stage exists once per difficulty (NORMAL/HARD/VERY HARD) with the same or fewer novels
            for s in stages.get(e["0"], []):
                ks = []
                if s.get("28"):
                    ks.append(s["28"])
                for en in sorted(enc.get(s["0"], []), key=lambda x: x.get("2", 0)):
                    for fld in ("8", "9"):
                        if en.get(fld):
                            ks.append(en[fld])
                ks = [k for k in dict.fromkeys(ks) if k in novels]
                stage_novels[s["0"]] = (s, ks)
                if ks and not seen.issuperset(ks):
                    seen.update(ks)
                    used.update(ks)
                    ep["stages"].append({"title": s.get("2", "").strip(), "novels": ks})
            if ep["stages"]:
                ad["episodes"].append(ep)
        # キャラクエ(2)/ふれあい(3) go under the per-character view; key = adventure.character.<code><n>
        if cat in (2, 3) and ad["episodes"]:
            code = re.sub(r"\d+$", "", a["1"].rsplit(".", 1)[-1])
            char_story[code]["quest" if cat == 2 else "fureai"] = ad
        # 衣装 (category 4) stories are played from each card in the card gallery instead
        if ad["episodes"] and cat not in HIDDEN_CATEGORIES:
            cats.setdefault(cat, []).append(ad)
    # ---- アルバム, as in the offline app: adventureEpisode f29 = section (1 周年ストーリー, 2 イベントストーリー),
    # f30 = order (descending), f6/f7 = 開催期間 (unix time); banner = episode_list_cell/<episode id>.png (605x140)
    album = {"anniversary": [], "event": []}
    episodes = table("adventureEpisode")
    has_album = any(e.get("29") for e in episodes)
    for e in episodes:
        sec_no, order = (e.get("29"), e.get("30", 0)) if has_album else ALBUM_DEFAULT.get(e["0"], (None, 0))
        sec = {1: "anniversary", 2: "event"}.get(sec_no)
        ep = ep_by_id.get(e["0"])
        if sec and ep and ep["stages"]:
            album[sec].append({"key": e["1"], "title": ep["title"], "order": order,
                               "start": e.get("6"), "end": e.get("7"),
                               "banner": find(f"files/adventure/episode_list_cell/{e['0']}.png"),
                               "stages": ep["stages"]})
    for v in album.values():
        v.sort(key=lambda x: -x["order"])
    json.dump(album, open(f"{WEB}/data/album.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("album", {k: len(v) for k, v in album.items()},
          "without banner", [x["title"] for v in album.values() for x in v if not x["banner"]])

    # ---- the story tree lists each story once: rerun ("復刻") episodes with the same story are merged
    # into the first, and episodes the album already holds become links to it. A rerun's <key>ex novels
    # are the same story as <key> when the dialogue matches (416 identical, 16 differ only in staging).
    def canon(k):
        return k[:-2] if k.endswith("ex") and k[:-2] in lines and lines[k] == lines[k[:-2]] else k

    def sig(ep):
        return tuple(canon(k) for st in ep["stages"] for k in st["novels"])

    album_at = {}
    for sec, v in album.items():
        for i, x in enumerate(v):
            album_at.setdefault(sig(x), (sec, i))
    merged = linked = 0
    for c, ads in cats.items():
        for ad in ads:
            kept, first = [], {}
            for ep in ad["episodes"]:
                sg = sig(ep)
                if sg in album_at:
                    sec, i = album_at[sg]
                    links = ad.setdefault("album", [])
                    if not any(l["sec"] == sec and l["i"] == i for l in links):
                        links.append({"title": album[sec][i]["title"], "sec": sec, "i": i})
                    linked += 1
                elif sg in first:
                    first[sg]["reruns"] = first[sg].get("reruns", 0) + 1
                    merged += 1
                else:
                    first[sg] = ep
                    kept.append(ep)
            ad["episodes"] = kept
        cats[c] = [ad for ad in ads if ad["episodes"] or ad.get("album")]
    print("story tree: reruns merged", merged, "episodes moved to album links", linked)
    tree = [{"name": CATEGORY.get(c, f"その他 {c}"), "id": c, "adventures": v} for c, v in cats.items()]

    others = collections.defaultdict(list)
    for k in novels:
        if k not in used:
            g = re.sub(r"[_\d]+$", "", k.split(".", 1)[-1])
            g = re.sub(r"^(co\d*)_[bh]_touch_.*", r"\1_touch", g)
            others[g].append(k)
    ui = {"menu1": find("files/offline/main_menu_bg01.png"), "menu2": find("files/offline/main_menu_bg02.png"),
          "credits": find("files/movie/offline_credit.mp4"),
          "chars": find("files/character/lottery/gac_1011003022/all_rectangle.png"),
          "cards": find("files/character/lottery/gac_1011001027/status_l.png"),
          "credits_bg": img.get("65980080")}
    json.dump({"tree": tree, "titles": novels, "ui": ui}, open(f"{WEB}/data/index.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump({g: sorted(v) for g, v in sorted(others.items())}, open(f"{WEB}/data/others.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("tree categories", len(tree), "novels in tree", len(used), "others", sum(len(v) for v in others.values()))
    build_movies(movie_refs, movie, novels)



    # ---- galleries
    chars = {r["1"].split(".", 1)[1]: r for r in table("character")}
    groups = collections.OrderedDict()
    for key, d in sorted(portrait.items()):
        info = portrait_info(d)
        if not info or not info["faces"]:
            continue
        code = key.split(".", 1)[1].split("_")[0]
        ch = chars.get(code, {})
        g = groups.setdefault(code, {"code": code, "name": ch.get("2", code), "short": ch.get("3", code), "items": []})
        g["items"].append({"key": key, **info})
    order = {r["1"].split(".", 1)[1]: i for i, r in enumerate(table("character"))}
    clist = sorted(groups.values(), key=lambda g: (order.get(g["code"], 9999), g["code"]))
    json.dump(clist, open(f"{WEB}/data/chars.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    cards = build_cards(stage_novels)

    # ---- per-character story view: 服裝(costume cards + their stories) + キャラクエ + ふれあい
    chars_tbl = {r["1"].split(".", 1)[1]: r for r in table("character")}
    corder = {r["1"].split(".", 1)[1]: i for i, r in enumerate(table("character"))}
    char_cost = collections.defaultdict(list)
    first_card = {}
    for c in cards:
        code = c["chara"]
        first_card.setdefault(code, c)
        if c.get("stories"):
            char_cost[code].append({"id": c["id"], "title": c["title"], "name": c["name"],
                                    "rarity": c["rarity"], "thumb": c["thumb"], "stories": c["stories"]})
    characters = []
    for code in sorted(set(char_cost) | set(char_story), key=lambda x: (corder.get(x, 9999), x)):
        r = chars_tbl.get(code, {})
        cs = char_story.get(code, {})
        fc = first_card.get(code, {})
        characters.append({"code": code, "name": r.get("2", code), "short": r.get("3", code),
                           "img": fc.get("bust") or fc.get("thumb"),
                           "costumes": char_cost.get(code, []),
                           "quest": cs.get("quest"), "fureai": cs.get("fureai")})
    json.dump(characters, open(f"{WEB}/data/characters.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("character views", len(characters), "with costumes",
          sum(1 for c in characters if c["costumes"]))

    meta = {"stats": [n for _, n in STATS], "gradeNormal": GRADE_NORMAL, "gradeAssist": GRADE_ASSIST,
            "gradeNames": GRADE_NAMES, "gradeIcon": find("files/icon/character_detial/evaluation_1.png"),
            "elements": {str(b): n for b, n in ELEMENTS.items()},
            # "another_gacha_op" is leftover data from another of the studio's games, not DanMemo's own, so only "argo".
            "gachaOp": {"argo": [find(f"files/movie/argo_gacha_op_0{n}.mp4") for n in (2, 3, 4)]},
            # where each reveal cut lives (asset roots differ per setup; an app-data backup splits them up)
            "gachaCuts": {n: c.rsplit("/", 1)[0] + "/" for n in
                          [f"argo_gacha_cut_03_flash_{r}" for r in (2, 3, 4)] + [f"argo_gacha_cut_07_{r}" for r in (1, 2, 3, 4)]
                          + ["argo_gacha_cut_04_moji_3"]
                          if (c := find(f"files/lwf/uiLwf/lottery/{n}/{n}.lwf"))},
            "gachaSe": {k: find(f"files/sound/se/ui/se_ui_gacha_{k}.ogg") for k in ("syuppin", "syuppin2", "cha", "dooropen")},
            # Anya (navi) rarity-foreshadow voice played over the waveform flash; longer = higher rarity.
            "gachaNavi": {"2": find("files/sound/voice/arn/voice_sys_gacha_arn_03.ogg"),
                          "3": find("files/sound/voice/arn/voice_sys_gacha_arn_04.ogg"),
                          "4": find("files/sound/voice/arn/voice_sys_gacha_arn_05.ogg")}}
    json.dump({**meta, "cards": cards}, open(f"{WEB}/data/gacha.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("portrait groups", len(clist), "portraits", sum(len(g["items"]) for g in clist), "cards", len(cards))
    # gacha-reveal name plates (needs Pillow + a CJK font); skip quietly if unavailable
    try:
        import gachanames
        gachanames.main_from_cards(cards)
    except Exception as e:
        print("name plates skipped:", e)


STATS = [(2, "力"), (16, "耐久"), (32, "器用"), (8, "敏捷"), (4, "魔力")]  # pcAbility field 7 bitmask

# Ability evaluation (letter) thresholds, read from libapp.so static init (0x720xxx, data @0x1bf40f0).
# Per stat (STATS order): descending [(evaluation index, minimum value)]; index 1=SSS … 12=I.
_G = lambda *t: [[i + 1, v] for i, v in enumerate(t)] + [[12, 0]]
_GB = lambda *t: [[i + 2, v] for i, v in enumerate(t)] + [[12, 0]]
GRADE_NORMAL = [_G(2000, 1000, 700, 400, 350, 300, 250, 200, 150, 100, 50),   # 力
                _G(1500, 750, 500, 230, 200, 170, 140, 110, 80, 50, 20),      # 耐久
                _G(1460, 730, 490, 230, 200, 170, 140, 110, 80, 50, 20),      # 器用
                _G(1400, 700, 470, 230, 200, 170, 140, 110, 80, 50, 20),      # 敏捷
                _G(1800, 900, 610, 320, 280, 240, 200, 160, 120, 80, 40)]     # 魔力
_BAL = _GB(500, 400, 280, 245, 210, 175, 140, 105, 70, 35)
# assists (pc field 9 == 4) use their own table; verified in-app (バランス型 adventurers use GRADE_NORMAL)
GRADE_ASSIST = [_BAL, _GB(500, 350, 200, 175, 150, 125, 100, 75, 50, 25), _BAL, _BAL, _BAL]
GRADE_NAMES = ["", "SSS", "SS", "S", "A", "B", "C", "D", "E", "F", "G", "H", "I"]
ELEMENTS = {1: "火", 2: "地", 4: "風", 8: "水", 16: "雷", 32: "光", 64: "闇"}


def build_cards(stage_novels):
    memorial = any(r.get("29") for r in table("adventureEpisode"))  # see main()
    """Card (pc) data for the card gallery: names, rarity, skills, abilities, status-board bonuses,
    limit-break bonuses and costume stories."""
    skill = {r["0"]: r for r in table("pcSkill")}
    abil = {r["0"]: r for r in table("pcAbility")}
    job = {r["0"]: r for r in table("pcJob")}
    aff = {r["1"]: r.get("2", "") for r in table("pcAffiliation")}
    cos = {r["0"]: r for r in table("characterCostume")}
    panels = collections.defaultdict(list)
    for r in table("pcAbilityPanel"):
        panels[r.get("1", 0)].append(r)
    for v in panels.values():
        v.sort(key=lambda r: r.get("2", 0))
    cos_stories = collections.defaultdict(list)
    for sid, (st, ks) in stage_novels.items():
        if st.get("15") and ks and str(st.get("7", "")).startswith("adventure_stage.costume") \
                and not set(ks) <= {k for x in cos_stories[st["15"]] for k in x["novels"]}:
            cos_stories[st["15"]].append({"title": st.get("2", "").strip(), "novels": ks})

    def sk(i, slot):
        r = skill.get(i)
        if not r:
            return None
        e = r.get("14") or 0
        return {"slot": slot, "name": r.get("1", ""), "desc": r.get("2", ""), "mp": r.get("5"),
                "icon": find(f"files/icon/character_detial/element_{e}.png") or find(f"files/icon/character_detial/element_{e & 127}.png")}

    def bonus(rows):
        tot = collections.Counter()
        for p in rows:
            a = abil.get(p.get("3"), {})
            if a.get("1") == 50:  # stat panel
                for bit, _ in STATS:
                    if a.get("7", 0) & bit:
                        tot[bit] += a.get("6", 0)
        return [tot[b] for b, _ in STATS]

    def element(r):
        """Card element = its special art's element bit (pcSkill field 14); else from skill text."""
        for f in ("28", "24", "25", "26", "22"):
            v = (skill.get(r.get(f), {}).get("14") or 0) & 127
            if v in ELEMENTS:
                return v
        txt = " ".join(skill.get(r.get(f), {}).get("2", "") or "" for f in ("28", "24", "25", "26"))
        m = re.search(r"(火|地|風|水|雷|光|闇)属性", txt)
        return {n: b for b, n in ELEMENTS.items()}[m.group(1)] if m else 0

    def job_type(j):
        t = re.sub(r"(の★\d+|_限界突破|★\d+)", "", j.get("1", "")) if j else ""
        return re.sub(r"^\d+周年", "", t)

    lvl = collections.defaultdict(dict)
    for r in table("pcLevelStep"):
        lvl[r.get("1")][r.get("2")] = r
    subl = collections.defaultdict(dict)
    for r in table("heroSublimateLevelStep"):
        if r.get("1") and r.get("7"):
            subl[r["1"]][r["7"]] = r
    TYPE = {1: "物理攻撃型", 2: "魔法攻撃型", 3: "回復型", 4: "バランス型", 5: "防御型"}
    # pc base-stat fields per STATS order (力, 耐久, 器用, 敏捷, 魔力); verified against the app
    BASE = [49, 52, 53, 51, 50]

    def calc(r, rank_jobs, lb_job):
        board = collections.Counter()
        for j in rank_jobs:
            for k, v in zip([n for _, n in STATS], bonus(panels.get(j.get("11"), []))):
                board[k] += v
        lbc = [bonus(panels.get(lb_job.get("11"), [])[: n * 5]) for n in range(1, 6)] if lb_job else []
        p = collections.Counter()
        for f in range(30, 40, 2):
            a = abil.get(r.get(str(f)), {})
            if a.get("5") == 16:  # percentage stat ability
                for bit, n in STATS:
                    if a.get("7", 0) & bit:
                        p[n] += a.get("6", 0)
        t = lvl.get(r.get("47"), {})
        hp_l, mp_l, hp, mp = {}, {}, 0, 0
        for L in range(1, 81):
            hp += t.get(L, {}).get("4", 0)
            mp += t.get(L, {}).get("10", 0)
            if L >= 60 and L % 4 == 0:
                hp_l[L], mp_l[L] = hp, mp
        sub = []
        g = subl.get(r.get("90"), {})
        acc = [0] * 7
        for step in range(1, 7):
            row = g.get(step)
            if not row:
                break
            # table order: HP, MP, 力, 魔力, 敏捷, 耐久, 器用 -> HP, MP, 力, 耐久, 器用, 敏捷, 魔力
            add = [row.get(k, 0) for k in ("8", "9", "10", "13", "14", "12", "11")]
            acc = [a + b for a, b in zip(acc, add)]
            sub.append(acc)
        return {"base": [r.get(str(f), 0) for f in BASE], "board": [board[n] for _, n in STATS], "lb": lbc,
                "pct": [p[n] for _, n in STATS], "hp0": r.get("48", 0), "mp0": r.get("54", 0),
                "hpL": hp_l, "mpL": mp_l, "subl": sub}

    out = []
    for r in table("pc"):
        rel = f"files/character/lottery/gac_{r['0']}/"
        img = find(rel + "status_l.png")
        if not img or r.get("1") == "テスト用" or r.get("9") not in (1, 4):
            continue
        rank_jobs = [job[r[f]] for f in ("14", "15", "16", "17", "18", "19") if r.get(f) in job]
        lb_job = job.get(r.get("20"))
        ranks = []
        for j in rank_jobs:
            ranks.append({"rank": j.get("4", 0), "bonus": bonus(panels.get(j.get("11"), []))})
        lb = []
        if lb_job:
            lp = panels.get(lb_job.get("11"), [])
            for n in range(1, 6):
                lb.append(bonus(lp[: n * 5]))
        abilities = []
        for f in range(29, 39, 2):
            a = abil.get(r.get(str(f + 1)))
            if a and a.get("2", "-") not in ("", "-"):
                abilities.append({"name": a.get("2", ""), "desc": a.get("3", ""), "order": r.get(str(f), 0)})
        if r.get("9") == 4:  # assist: one assist skill, "+" at max rank, "++" at limit break 5
            skills = [x for x in (sk(r.get("25"), "アシストスキル"), sk(r.get("26"), "アシストスキル（限界突破5）")) if x]
        else:  # as the app's skill page: 必殺技, 技 ×3 (normal attack / counter are not shown there)
            skills = [x for x in (sk(r.get("28"), "必殺技"), sk(r.get("24"), "技"), sk(r.get("25"), "技"),
                                  sk(r.get("26"), "技")) if x]
        c = cos.get(r.get("76"), {})
        out.append({
            "id": r["0"], "title": r.get("1", ""), "name": r.get("2", ""), "rarity": r.get("46", 0),
            "kind": "adv" if r.get("9") == 1 else "assist", "chara": r.get("7", "").split(".")[-1],
            "affiliation": aff.get(r.get("13"), ""), "type": TYPE.get(r.get("12"), "") if r.get("9") == 1 else "",
            # pc[92] = element bit (agrees with skills on 480/487 cards; authoritative); pc[96] = 英雄祭
            "typeId": r.get("12", 0), "limited": bool(r.get("78")), "heroFes": bool(r.get("96")),
            "element": (r.get("92") or 0) if r.get("9") == 1 else 0,
            "elementIcon": find(f"files/icon/character_detial/element_{r.get('92')}.png") if r.get("92") and r.get("9") == 1 else None,
            "fx": {k: v for k, v in ((k, find(f"files/lwf/lotteryLwf/lwf_lottery_ef_{r['0']}/lwf_ui_ef_{r['0']}_{k}.lwf"))
                                     for k in ("status_l", "rectangle", "lottery")) if v},
            "lotteryImg": find(rel + "lottery.png"),
            # gacha reveal (art/upcut from the global backup's CDN paths, voice = Japanese original)
            "gacha": {"art": find(rel + "lottery.png"), "silhouette": find(rel + "white.png"),
                      "voice": gacha_voice(r.get("75")),
                      # official name plate: the global client ships an English one per card; for JP
                      # only the early cards' survive (fill_gaps.py → name_jp/). Otherwise
                      # gachanames.py draws one from the card data
                      "plate": find(f"files/lottery/name_jp/{r['0']}.png") if memorial
                               else find(f"files/lottery/name/{r['0']}.png"),
                      # the card's line as a vertical-text image, shown by the moji cut (same sources)
                      "text": find(f"files/lottery/text_jp/{r['0']}.png") if memorial
                              else find(f"files/lottery/text/{r['0']}.png")},
            "calc": calc(r, rank_jobs, lb_job),
            "skills": skills, "abilities": abilities, "ranks": ranks, "limitbreak": lb,
            "costume": {"name": c.get("3", ""), "desc": c.get("4", "")} if c else None,
            "stories": cos_stories.get(r["0"], []),
            "img": img, "thumb": find(rel + "thumbnail_gacha.png") or img,
            "big": find(rel + "all_rectangle.png"), "bust": find(rel + "bustup_s.png"),
        })
    out.sort(key=lambda c: (c["kind"] != "adv", c["id"]))
    return out


if __name__ == "__main__":
    main()
