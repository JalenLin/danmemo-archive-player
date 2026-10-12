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
        try:
            os.symlink(disk, os.path.join(rdir, str(i)))
        except OSError:  # Windows without the symlink right: tools/serve.py maps /r/<i>/ to the root itself
            pass
        roots.append((f"r/{i}/", disk.rstrip("/").rstrip("\\") + "/"))
    return roots


ROOTS = link_roots()
VOICE = {}
GACHA_VOICE_ALIAS = {}
# Cards whose line image exists but whose pc field 75 is empty in both the JP and the global master data;
# the recording is there, unassigned. Matched by transcribing the character's unassigned gachahit voices
# (Whisper) against the card's line: 夕涼聖女 "聖女とは一体……恥ずかしい！", 白巫女 "レフィーヤ。この魔法を
# お前に託す。", 鏡花水月 "まずは武器を集めてこないと". Every other card with a line has its voice.
CARD_VOICE_FIX = {1011043006: "voice.sys_gachahit_amd_16", 1011019001: "voice.sys_gachahit_fil_04",
                  1011014002: "voice.sys_gachahit_cgs_05"}


def gacha_voice(f75):
    """Resolve a card's gacha-hit voice (pc field 75) to a served path: the dedicated recording if
    present, else the story voice the voice table points it at."""
    if not f75:
        return None
    direct = VOICE.get("voice_" + f75.split(".", 1)[1])
    return direct or VOICE.get(GACHA_VOICE_ALIAS.get(f75, ""))

# The memorial app's album picks 48 of the original events (adventureEpisode f29 = section, f30 = order).
# Other app data (e.g. the global client's) has the same episodes but not this selection; use it then.
# Preview / home-base ("拠点") novels the game played at start-up for a while (startNovel), mapped to the
# event episode they belong to: novel.nextnotice_<n> -> adventureEpisode id. Matched by run dates, title,
# dialogue and reused event voice lines, then checked by hand (anniversary series by part; reruns -> the
# original). The rest (anime-episode countdowns, new year, tests, feature intros) get their own dated list.
NEXTNOTICE_EVENT = {
    2: 7090000901, 5: 7090001101, 6: 7090001201, 8: 7090001401,
    10: 7090001501, 11: 7090001601, 12: 7090001701, 14: 7090001801,
    15: 7160000101, 16: 7160000101, 19: 7090002001, 22: 7090002101,
    27: 7090002501, 28: 7090002701, 29: 7090002801, 31: 7090003101,
    32: 7090120210, 33: 7090003301, 37: 7090003401, 38: 7090003601,
    39: 7090003701, 40: 7090004001, 54: 7160000201, 55: 7160000301,
    60: 7090004301, 61: 7090004501, 62: 7090004701, 63: 7090005101,
    65: 7090004901, 66: 7090005301, 68: 7010000505, 69: 7090005501,
    70: 7090005901, 71: 7090006001, 72: 7090006201, 73: 7090006301,
    74: 7160000401, 75: 7160000501, 76: 7160000601, 77: 7090006401,
    89: 7090006601, 90: 7090006701, 91: 7090006801, 93: 7090007101,
    95: 7090007301, 96: 7090007501, 97: 7090007901, 98: 7090007701,
    99: 7160000701, 100: 7160000801, 101: 7160000901, 102: 7090008501,
    103: 7090008701, 104: 7090008901, 105: 7090009101, 106: 7090009301,
    107: 7090009401, 109: 7160001001, 110: 7090009601, 111: 7010000516,
    112: 7010000522, 113: 7160001301, 114: 7160001401, 126: 7160001501,
    127: 7090010201, 128: 7010000526, 130: 7090010501, 131: 7090010701,
    134: 7090010901, 135: 7090010801, 147: 7010000532, 148: 7010000543,
    149: 7160001901, 150: 7160002001, 151: 7160002101,
    # anniversaries: the 1st-anniversary "DanMemo FES 2018" announcement; the daily countdown to the 2nd
    # anniversary (2019-06-07..18), whose last part leads into Argonaut
    17: 7090001801,
    42: 7160000201, 43: 7160000201, 44: 7160000201, 45: 7160000201, 46: 7160000201, 47: 7160000201,
    48: 7160000201, 49: 7160000201, 50: 7160000201, 51: 7160000201, 52: 7160000201, 53: 7160000201,
}

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
# album tabs beyond the memorial app's own two: section -> event categories whose dated episodes it collects
#   extra = story events incl. short stories, map and raid events; advent = descent (降臨) events
EXTRA_ALBUM = {"extra": {9, 16, 17}, "advent": {8}, "rerun": set()}  # rerun: any of those whose title says so
# a rerun as this data's own title marks it (the global server's first runs of JP reruns carry no marker)
RERUN_RE = re.compile(r"復刻|\bre-?run\b", re.I)


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


def native_md5s():
    """md5s of the files this setup's own manifests list (config "manifests" + "legacy_manifests"). With
    "fallback_manifests" configured, another region's files can land in the asset roots; a JP build uses
    this to show only list cells that are its own (Japanese) artwork."""
    out = set()
    pats = CFG["manifests"] + [os.path.join(CFG["legacy_manifests"], "*", "*.manifest*")]
    for f in [f for p in pats for f in glob.glob(p) if os.path.isfile(f)]:
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        out.update(v["md5"] for v in (d.get("assets") or {}).values())
        out.update(v["md5"] for v in list(d.get("singleImages", {}).values()) + list(d.get("episodes", {}).values()))
    return out


def is_native(rel, md5s):
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

# Home-screen / town voice lines kept as "novels" (one line each): touch, greetings, idle talk, the
# communication page and town chatter. They are listed per character, not as stories.
#   co_ / co02_ / co03_ (sys_ / sys02_ / sys03_) = the version spoken to Bell / Ais / Lefiya
INTERACTION_RE = re.compile(r"^novel\.(?:co\d*_(?:[hb]_touch|[dmn]_greet|talk|hold)|reaction|sys\d*_town(?:_talk)?)_([a-z]+)_")
INTERACTION = {}
VOICE_TO = {"": "ベル向け", "02": "アイズ向け", "03": "レフィーヤ向け"}
VOICE_CATS = ["ログイン", "交流ページ", "挨拶", "タッチ", "交流", "放置", "街", "アラーム", "衣装チェンジ", "システム"]


def voice_kind(name):
    """(category, sub label, addressee, character code) for a voice/novel name like co02_b_touch_ais_01."""
    m = re.match(r"(?:novel\.|voice\.)?co(\d*)_([hb])_touch_([a-z]+)_", name)
    if m:
        return "タッチ", {"h": "頭", "b": "体"}[m.group(2)], VOICE_TO.get(m.group(1), ""), m.group(3)
    m = re.match(r"(?:novel\.|voice\.)?co(\d*)_([dmn])_greet_([a-z]+)_", name)
    if m:
        return "挨拶", {"m": "朝", "d": "昼", "n": "夜"}[m.group(2)], VOICE_TO.get(m.group(1), ""), m.group(3)
    m = re.match(r"(?:novel\.|voice\.)?co(\d*)_(talk|hold)_([a-z]+)_", name)
    if m:
        return {"talk": "交流", "hold": "放置"}[m.group(2)], "", VOICE_TO.get(m.group(1), ""), m.group(3)
    m = re.match(r"(?:novel\.|voice\.)?reaction_([a-z]+)_([a-z]+)_", name)
    if m:
        return "交流ページ", {"morning": "朝", "noon": "昼", "evening": "夕", "night": "夜"}.get(m.group(2), m.group(2)), "", m.group(1)
    m = re.match(r"(?:novel\.|voice\.)?sys(\d*)_town(?:_talk)?_([a-z]+)_", name)
    if m:
        return "街", "", VOICE_TO.get(m.group(1), ""), m.group(2)
    return None


def build_voices(chars_tbl):
    """data/voices.json: per character, the home/town voice lines (text from the novels and the master
    tables, audio from this setup's own assets), plus voice files with no text anywhere (listed as such)."""
    per = collections.defaultdict(list)  # code -> items
    seen = set()

    def add(code, cat, sub, to, text, vref, order):
        path = VOICE.get("voice_" + vref.split(".", 1)[1]) if vref else None
        if vref:
            seen.add("voice_" + vref.split(".", 1)[1])
        per[code].append({"cat": cat, "sub": sub, "to": to, "text": text, "voice": path, "o": order})

    for key, (text, vref) in sorted(INTERACTION.items()):
        k = voice_kind(key)
        if k:
            add(k[3], k[0], k[1], k[2], text, vref, key)
    for code, r in chars_tbl.items():  # login lines + system calls (character table)
        for tf, vf in (("9", "16"), ("10", "17")):
            if r.get(vf):
                add(code, "ログイン", "", "", r.get(tf, ""), r[vf], vf)
        for vf, label in (("18", "タイトルコール"), ("19", "ステータス"), ("20", "ステータス"), ("21", "フレンド"),
                          ("22", "プレゼント"), ("23", "プレゼント")):
            if r.get(vf):
                add(code, "システム", label, "", "", r[vf], vf)
    for r in table("alarmVoice"):
        code = re.sub(r"\d+$", "", r.get("1", "").split(".", 1)[-1])
        if r.get("10"):
            add(code, "アラーム", r.get("2", ""), "", r.get("3", ""), r["10"], r["0"])
    for r in table("characterCostume"):
        code = r.get("1", "").split(".", 1)[-1]
        if r.get("7"):
            add(code, "衣装チェンジ", r.get("3", ""), "", "", r["7"], r["0"])
    # voice files this setup has (e.g. from an old build's manifest) that no text points at
    for base, path in sorted(VOICE.items()):
        if base in seen:
            continue
        k = voice_kind(base[6:])
        if k:
            per[k[3]].append({"cat": k[0], "sub": k[1], "to": k[2], "text": "", "voice": path, "o": base})
    out = {}
    for code, items in per.items():
        if not any(i["voice"] or i["text"] for i in items):
            continue
        items.sort(key=lambda i: (VOICE_CATS.index(i["cat"]), list(VOICE_TO.values()).index(i["to"]) if i["to"] in VOICE_TO.values() else 9, i["sub"], str(i["o"])))
        out[code] = [{k: v for k, v in i.items() if k != "o" and v != ""} for i in items]
    json.dump(out, open(f"{WEB}/data/voices.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    n = sum(len(v) for v in out.values())
    print("voices: characters", len(out), "lines", n, "with audio", sum(1 for v in out.values() for i in v if i.get("voice")),
          "with text", sum(1 for v in out.values() for i in v if i.get("text")))
    return out


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
    # Some gacha-hit voices reuse a story recording: the voice table points them at that file.
    GACHA_VOICE_ALIAS = {}
    for r in table("voice"):
        k, f = str(r.get("1", "")), os.path.basename(str(r.get("2", "")))
        if k.startswith("voice.sys_gachahit") and f and f != "voice_" + k[6:]:
            GACHA_VOICE_ALIAS[k] = f
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
    interaction = {}  # novel key -> (line, voice ref) for the per-character voice lists (not stories)
    movie_refs = collections.defaultdict(list)  # movie_usm key -> [(novel id, novel key)] for the movie page
    lines = {}  # novel key -> its dialogue, to recognise rerun copies
    missing = collections.Counter()
    gaps = {}  # novel key -> {kind: count} of assets no source has (shown in the player and the lists)
    GAP_KIND = {"single_image": "img", "movie_usm": "movie", "novel_portrait": "chara", "scenario_lwf": "fx",
                "battle_effect": "fx", "voice": "voice", "bgm": "sound", "se": "sound"}
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
            if c["2"] == 8 and len(args) > 4 and f"manpu.{args[4]}" not in res:  # emotion mark icon
                res[f"manpu.{args[4]}"] = find(f"files/icon/novel/manpu_{args[4]}.png")
            for a in args:
                for tok in re.split(r"[\s,]+", a):
                    if tok.startswith("movie_usm.") and (nid, key) not in movie_refs[tok]:
                        movie_refs[tok].append((nid, key))
                    if keyre.match(tok) and tok not in res:
                        r = resolve(tok)
                        res[tok] = r
                        if r is None:
                            missing[tok.split(".")[0]] += 1
        g = collections.Counter(GAP_KIND[t.split(".")[0]] for t, v in res.items() if v is None and t.split(".")[0] in GAP_KIND)
        doc = {"key": key, "title": title, "cmds": out, "res": res}
        if g:
            doc["gaps"] = gaps[key] = dict(g)
        json.dump(doc, open(f"{WEB}/data/novel/{key}.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        novels[key] = title
        lines[key] = tuple(c[-1] for c in out if c[0] in (11, 12, 45) and len(c) > 1)
        if INTERACTION_RE.match(key):
            vref = next((t for t in res if t.startswith("voice.")), None)
            interaction[key] = ("\n".join(c[-1] for c in out if c[0] in (11, 12, 45) and len(c) > 1), vref)
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
    native = native_md5s() if memorial and CFG["fallback_manifests"] else None
    for a in adv:
        cat = a.get("2")
        ad = {"title": a.get("4", "").strip(), "key": a["1"], "episodes": []}
        for e in eps.get(a["0"], []):
            ep = ep_by_id[e["0"]] = {"title": e.get("4", "").strip(), "sub": e.get("5", "").strip(), "stages": []}
            if e.get("6") and e.get("7"):  # 開催期間 (unix time)
                ep["start"], ep["end"] = e["6"], e["7"]
            rel = f"files/adventure/episode_list_cell/{e['0']}.png"
            # the memorial app ships only the album's cells; others come from the configured manifests
            if native is None or is_native(rel, native):
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
    # ---- side stories the event unlocked as you levelled its rental character (pcGuestLevelStep), added to
    # that event (pcGuest f7) after its own stages, under the titles the table gives them
    guest_ep = {r["0"]: r.get("7") for r in table("pcGuest")}
    for r in sorted(table("pcGuestLevelStep"), key=lambda r: (r.get("1", 0), r.get("2", 0))):
        ep, k = ep_by_id.get(guest_ep.get(r.get("1"))), r.get("9")
        if ep and k in novels and k not in used:
            ep["stages"].append({"title": r.get("10", "").strip() or novels[k], "novels": [k]})
            used.add(k)
    # ...and follow-up parts (<key>_01, _02…) of a story an episode already has, right after it
    for k in sorted(novels):
        m = re.match(r"(.+)_(\d\d)$", k)
        if not m or k in used or m.group(1) not in used:
            continue
        for ep in ep_by_id.values():
            for st in ep["stages"]:
                if m.group(1) in st["novels"]:
                    st["novels"].insert(st["novels"].index(m.group(1)) + 1, k)
                    used.add(k)
                    break
            if k in used:
                break

    # ---- preview / home-base novels: attach to their event, list the rest by date
    notice_run = {}
    for r in table("startNovel"):
        k = r.get("1", "")
        if k.startswith("novel.nextnotice_"):
            a0, b0 = notice_run.get(k, (None, None))
            notice_run[k] = (min(x for x in (a0, r.get("2")) if x) if (a0 or r.get("2")) else None,
                             max(x for x in (b0, r.get("3")) if x) if (b0 or r.get("3")) else None)
    for n, eid in NEXTNOTICE_EVENT.items():
        k = f"novel.nextnotice_{n:05d}"
        if k in novels and eid in ep_by_id:
            ep_by_id[eid].setdefault("notices", []).append({"key": k, "title": novels[k]})
            used.add(k)
    for ep in ep_by_id.values():  # in the order the game played them
        if ep.get("notices"):
            ep["notices"].sort(key=lambda n: (notice_run.get(n["key"], (None,))[0] or 0, n["key"]))
    notices = sorted(({"key": k, "title": novels[k], "start": notice_run.get(k, (None, None))[0], "end": notice_run.get(k, (None, None))[1]}
                      for k in novels if k.startswith("novel.nextnotice_") and k not in used),
                     key=lambda x: (x["start"] or 0, x["key"]))
    for x in notices:
        used.add(x["key"])
    # TV-anime previews get a list per season: "3期5話放映前拠点" …; the 2019 countdown is season 2
    groups = collections.OrderedDict([("misc", [])])
    for x in notices:
        m = re.search(r"(\d)期", x["title"])
        season = m.group(1) if m else "2" if "アニメカウントダウン" in x["title"] else None
        groups.setdefault(f"anime{season}" if season else "misc", []).append(x)
    groups = collections.OrderedDict([("misc", groups.pop("misc"))] + sorted(groups.items()))
    json.dump(groups, open(f"{WEB}/data/notices.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("preview novels: on events", sum(len(e.get("notices", [])) for e in ep_by_id.values()),
          "dated lists", {k: len(v) for k, v in groups.items()})

    # ---- the story tree lists each story once: rerun ("復刻") episodes with the same story are merged
    # into the first, and episodes the album holds are left out (categories left empty disappear). A rerun's <key>ex novels
    # are the same story as <key> when the dialogue matches (416 identical, 16 differ only in staging).
    def canon(k):
        return k[:-2] if k.endswith("ex") and k[:-2] in lines and lines[k] == lines[k[:-2]] else k

    def sig(ep):
        return tuple(canon(k) for st in ep["stages"] for k in st["novels"])

    album = {"anniversary": [], "event": [], **{k: [] for k in EXTRA_ALBUM}}
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
                               "stages": ep["stages"], "notices": ep.get("notices", [])})
    # extra tabs: events the memorial album leaves out — every episode of those categories with a run period
    # whose story no album entry holds yet (reruns with changed content get their own tab; newest first)
    adv_cat = {a0["0"]: a0.get("2") for a0 in table("adventure")}
    taken = {sig(x) for sec in ("anniversary", "event") for x in album[sec]}
    absorbed = collections.defaultdict(list)  # album entry -> signatures of episodes merged into it
    for e in sorted(episodes, key=lambda e: (e.get("6") or 0, e["0"])):
        ep = ep_by_id.get(e["0"])
        sec = next((k for k, cs in EXTRA_ALBUM.items() if adv_cat.get(e.get("2")) in cs), None)
        if sec and ep and RERUN_RE.search(ep["title"]):
            sec = "rerun"  # reruns whose story differs from the original (e.g. added EX stories)
        if (sec and e.get("6") and e.get("7") and not e.get("29")
                and e["0"] not in ALBUM_DEFAULT and ep and ep["stages"] and sig(ep) not in taken):
            # a later phase of an event the album already has (same title, same story series, e.g. the
            # raid finale of グランド・デイ): append its stages to that entry instead of a new one
            series = {re.sub(r"_\d+(ex)?$", "", k) for st in ep["stages"] for k in st["novels"]}
            host = next((x for v in album.values() for x in v if x["title"] == ep["title"]
                         and series & {re.sub(r"_\d+(ex)?$", "", k) for st in x["stages"] for k in st["novels"]}), None)
            if host:
                absorbed[id(host)] += [sig(host), sig(ep)]  # the story tree still knows both halves
                host["stages"] = host["stages"] + [st for st in ep["stages"] if st not in host["stages"]]
                taken.add(sig(ep))
                continue
            taken.add(sig(ep))
            album[sec].append({"key": e["1"], "title": ep["title"], "order": e["6"], "start": e["6"], "end": e["7"],
                                   "banner": ep.get("banner"), "stages": ep["stages"], "notices": ep.get("notices", [])})
    # an album entry also shows the preview novels of story-tree episodes that hold the same stories
    by_novel = collections.defaultdict(list)
    for ep in ep_by_id.values():
        for n in ep.get("notices", []):
            for st in ep["stages"]:
                for k in st["novels"]:
                    if n not in by_novel[k]:
                        by_novel[k].append(n)
    for v in album.values():
        for x in v:
            for st in x["stages"]:
                for k in st["novels"]:
                    for n in by_novel.get(k, []):
                        if n not in x["notices"]:
                            x["notices"].append(n)
    for v in album.values():
        v.sort(key=lambda x: -x["order"])
    json.dump(album, open(f"{WEB}/data/album.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("album", {k: len(v) for k, v in album.items()},
          "without banner", [x["title"] for v in album.values() for x in v if not x["banner"]])

    album_at = {}
    for sec, v in album.items():
        for i, x in enumerate(v):
            for sg in [sig(x)] + absorbed.get(id(x), []):
                album_at.setdefault(sg, (sec, i))
    merged = linked = 0
    for c, ads in cats.items():
        for ad in ads:
            kept, first = [], {}
            for ep in ad["episodes"]:
                sg = sig(ep)
                if sg in album_at:  # the album has it: leave it out of the story tree
                    linked += 1
                elif sg in first:
                    first[sg]["reruns"] = first[sg].get("reruns", 0) + 1
                    merged += 1
                else:
                    first[sg] = ep
                    kept.append(ep)
            ad["episodes"] = kept
        cats[c] = [ad for ad in ads if ad["episodes"]]
    cats = {c: ads for c, ads in cats.items() if ads}
    print("story tree: reruns merged", merged, "episodes left to the album", linked)
    tree = [{"name": CATEGORY.get(c, f"その他 {c}"), "id": c, "adventures": v} for c, v in cats.items()]

    elsewhere = {r.get("5") for r in table("characterPresentCharacterInfo")}  # shown on the character pages
    others = collections.defaultdict(list)
    for k in novels:
        if k not in used and k not in interaction and k not in elsewhere:
            g = re.sub(r"[_\d]+$", "", k.split(".", 1)[-1])
            g = re.sub(r"^(co\d*)_[bh]_touch_.*", r"\1_touch", g)
            others[g].append(k)
    # home tiles: the memorial app's menu art, else story CGs every client has (global data lacks files/offline/)
    ui = {"menu1": find("files/offline/main_menu_bg01.png") or img.get("65010001"),
          "menu2": find("files/offline/main_menu_bg02.png") or img.get("65010002"),
          "credits": find("files/movie/offline_credit.mp4"),
          "chars": find("files/character/lottery/gac_1011003022/all_rectangle.png"),
          "cards": find("files/character/lottery/gac_1011001027/status_l.png"),
          "credits_bg": img.get("65980080")}
    # stories whose pictures / movies / portraits / effects no source has (the list marks them; voices and sounds
    # alone don't count: the scene still plays)
    shown_gaps = {k: v for k, v in gaps.items() if any(x in v for x in ("img", "movie", "chara", "fx"))}
    print("stories with missing pictures/movies/portraits/effects", len(shown_gaps), "| with any gap", len(gaps))
    json.dump({"tree": tree, "titles": novels, "ui": ui, "gaps": shown_gaps}, open(f"{WEB}/data/index.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    json.dump({g: sorted(v) for g, v in sorted(others.items())}, open(f"{WEB}/data/others.json", "w", encoding="utf-8"),
              ensure_ascii=False, separators=(",", ":"))
    print("tree categories", len(tree), "novels in tree", len(used), "others", sum(len(v) for v in others.values()))
    build_movies(movie_refs, movie, novels)
    global INTERACTION
    INTERACTION = interaction



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
    voices = build_voices(chars_tbl)
    # gift-event stories (e.g. the Valentine plan): characterPresentCharacterInfo f2 = character id, f5 = novel
    code_of = {r["0"]: r["1"].split(".", 1)[1] for r in table("character")}
    # titles from the event table (localised: プレゼントイベント / Present Event); the novels' own names are
    # internal and stay Japanese even in the global data
    pinfo = {r["0"]: r for r in table("characterPresentInfo")}
    present = collections.defaultdict(list)
    for r in table("characterPresentCharacterInfo"):
        k, code = r.get("5"), code_of.get(r.get("2"))
        if k and code and k in novels and k not in [x["key"] for x in present[code]]:
            ev = pinfo.get(r.get("1"), {})
            present[code].append({"key": k, "title": ev.get("1") or novels[k], "start": ev.get("2"), "end": ev.get("3")})
    characters = []
    for code in sorted(set(char_cost) | set(char_story) | set(present) | (set(voices) & set(chars_tbl)), key=lambda x: (corder.get(x, 9999), x)):
        r = chars_tbl.get(code, {})
        cs = char_story.get(code, {})
        fc = first_card.get(code, {})
        characters.append({"code": code, "name": r.get("2", code), "short": r.get("3", code),
                           "img": fc.get("bust") or fc.get("thumb"),
                           "costumes": char_cost.get(code, []),
                           "quest": cs.get("quest"), "fureai": cs.get("fureai"), "voices": len(voices.get(code, [])),
                           "present": present.get(code, []),
                           "profile": {k: r.get(f) for k, f in (("cv", "7"), ("race", "11"), ("title", "12"), ("age", "13"),
                                                                ("height", "14"), ("desc", "5")) if r.get(f)}})
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
                          + ["argo_gacha_cut_04_moji_3", "argo_gacha_cut_06_4"]
                          if (c := find(f"files/lwf/uiLwf/lottery/{n}/{n}.lwf"))},
            "gachaSe": {k: find(f"files/sound/se/ui/se_ui_gacha_{k}.ogg") for k in ("syuppin", "syuppin2", "cha", "dooropen")},
            # card-reveal music, matched against a recording of the original: ★2 "cha", ★3 get1, ★4 get2 from
            # the upcut close-up (cut_06; a quiet 2.6 s intro, then the fanfare under cut_07) or get3 = the same
            # fanfare without the intro. The files sit in bgm/ or se/ui/ depending on the client version.
            "gachaFanfare": {k: find(f"files/sound/bgm/bgm_fanfare_gacha_{k}.ogg") or find(f"files/sound/se/ui/bgm_fanfare_gacha_{k}.ogg")
                             for k in ("get1", "get2", "get3")},
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
                      "upcut": find(rel + "lottery_upcut.png"),  # ★4 close-up sweep (cut_06)
                      "voice": gacha_voice(r.get("75") or CARD_VOICE_FIX.get(r["0"])),
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
