"""Download assets the stories (and the album, cards) use but no configured asset root has, from the CDN.

md5/path sources, all from config.json and in this order: the setup's own manifests ("manifests", default
the memorial app's cdn/project.manifest*), old JP online builds' manifests ("legacy_manifests", see
tools/legacy_manifests.py; newest build first), the manifests an app-data backup ships inside its asset
roots (contents/N/project.manifest, contents/1/manifests/*), and only if you list them, another region's
manifests ("fallback_manifests" — their files may carry that region's language). Nothing else in the
project is read, so a Japanese setup never picks up global files and vice versa.
The set of files is driven by what the built data references (novels, album folders) plus the cards and
the gacha reveal (art, cuts, opening movies — converted to .mp4 via usm.py — and gacha-hit voices), and
the event-voice zips of episodes no root has unpacked (unpacked into files/sound/voice_episode/), and the
home/town/system voices shown on the character pages.
Files any other configured asset root already has are never downloaded, and a download that would shadow
a different copy in another root is removed. Story CGs already on disk are kept (other builds only
re-encode them). Resumable (skips files already present with the right md5), parallel.
JP data also gets the official Japanese gacha name plates and line images — from the legacy manifests,
else from an early (2017-07) pre-md5 snapshot — stored as files/lottery/{name_jp,text_jp}/<id>.png so they
never mix with the global client's English ones (files/lottery/{name,text}/).
Usage: python tools/fill_gaps.py [--dry]
"""
import glob
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

CFG = config.load()
ASSETS = CFG["downloads"]  # downloads go here; keep it in config.json's asset_roots
# every other configured asset root counts as "already have it" (the APK, an app-data backup, ...)
OTHER_ROOTS = [r for r in CFG["asset_roots"] if os.path.abspath(r) != os.path.abspath(ASSETS)]
CDN = "https://cdn-danmemo.akamaized.net/"
DRY = "--dry" in sys.argv
# the only pre-md5 asset snapshot known (found once in the Wayback Machine): <CDN>/<sha1>/contents/<path>
LEGACY = CDN + "cc73f149fe44ec2287359e6b7f4e2c1e5fdb7b03/contents/"


def man_table(name):
    return json.load(open(f"{CFG['dec']}/master/{name}.json", encoding="utf-8"))["0"]


def manifest_entries(path):
    """{logical path: {md5, path, size}} from a project/phase manifest, or the single_image /
    voice_episode manifests (keyed by id, logical path = the CDN path without contents/ and md5)."""
    try:
        d = json.load(open(path))
    except (OSError, ValueError):
        return {}
    if "assets" in d:
        return d["assets"]
    out = {}
    for v in list(d.get("singleImages", {}).values()) + list(d.get("episodes", {}).values()):
        m = re.match(r"contents/(.+)/[0-9a-f]{32}\.\w+$", v.get("path", ""))
        if m:
            out[m.group(1)] = v
    return out


def _files(patterns):
    return [f for p in patterns for f in sorted(glob.glob(p)) if os.path.isfile(f)]


def _ver(d):
    return [int(x) if x.isdigit() else 0 for x in os.path.basename(d).split(".")]


# full manifest: key -> {md5, path, size}; earlier sources win
MAN, OWN, LEGACY_MAN = {}, {}, {}
for f in _files(CFG["manifests"]):
    for k, v in manifest_entries(f).items():
        OWN.setdefault(k, v)
for d in sorted(glob.glob(os.path.join(CFG["legacy_manifests"], "*", "")), key=lambda d: _ver(d.rstrip("/")), reverse=True):
    for f in sorted(glob.glob(d + "*.manifest*")):
        for k, v in manifest_entries(f).items():
            LEGACY_MAN.setdefault(k, v)
BACKUP = _files([os.path.join(r, "project.manifest") for r in CFG["asset_roots"]]
                + [os.path.join(r, "manifests", "*.manifest") for r in CFG["asset_roots"]])
for src in [OWN, LEGACY_MAN] + [manifest_entries(f) for f in BACKUP + _files(CFG["fallback_manifests"])]:
    for k, v in src.items():
        MAN.setdefault(k, v)
FALLBACK_KEYS = set(MAN) - set(OWN) - set(LEGACY_MAN) - {k for f in BACKUP for k in manifest_entries(f)}
BYBASE = {}
for k in MAN:
    BYBASE.setdefault(os.path.basename(k).rsplit(".", 1)[0], []).append(k)


def add(targets, key):
    if key in MAN:
        targets.add(key)


def under(targets, prefix):
    for k in MAN:
        if k.startswith(prefix):
            targets.add(k)


def collect():
    t = set()
    # master maps for id/name resolution
    single = {r["2"]: r["0"] for r in man_table("singleImage")}
    bgm = {r["1"]: r["2"] for r in man_table("bgm")}
    se = {r["1"]: r["2"] for r in man_table("se")}
    slwf = {r["1"]: r["0"] for r in man_table("scenarioLwf")}
    battle = {r["5"]: r["0"] for r in man_table("battleEffect") if r.get("5")}
    movie = {r["1"]: r["2"] for r in man_table("movieUsm")}

    # 1) assets referenced by the offline novels
    kre = re.compile(r"^(single_image|bgm|se|voice|scenario_lwf|battle_effect|movie_usm)\.")
    refs = set()
    for f in glob.glob(f"{CFG['web']}/data/novel/*.json"):
        d = json.load(open(f))
        for c in d.get("cmds", []):
            if isinstance(c, list):
                for v in c:
                    if isinstance(v, str) and kre.match(v):
                        refs.add(v)
    for key in refs:
        kind, _, name = key.partition(".")
        if kind == "voice":
            for mk in BYBASE.get("voice_" + name, []):
                add(t, mk)
        elif kind == "single_image" and key in single:
            for mk in BYBASE.get(str(single[key]), []):
                if "/single_image/" in mk:
                    add(t, mk)
        elif kind == "bgm" and key in bgm:
            for mk in BYBASE.get(bgm[key].split("/")[-1], []):
                add(t, mk)
        elif kind == "se" and key in se:
            for mk in BYBASE.get(se[key].split("/")[-1], []):
                add(t, mk)
        elif kind == "scenario_lwf" and key in slwf:
            under(t, f"files/lwf/scenarioLwf/{slwf[key]}/")
        elif kind == "battle_effect" and key in battle:
            under(t, f"files/lwf/battleLwf/{battle[key]}/")
        elif kind == "movie_usm" and key in movie:
            for ext in (".usm", ".mp4"):
                add(t, f"files/movie/{movie[key]}{ext}")

    # 2) event-album banners / cells (not novel-referenced, wanted for the album view)
    for pre in ["files/adventure/episode_banner/", "files/adventure/half_banner/",
                "files/adventure/element_event_banner/", "files/event_box/banner/",
                "files/ui/anniversary/", "files/adventure/stage_list_cell/",
                "files/adventure/episode_list_cell/"]:
        under(t, pre)
    # 3) global data: the official per-card gacha name plates and line images (English text; the JP memorial app has
    #    none and draws its own with gachanames.py, so skip them there)
    if not any(r.get("29") for r in man_table("adventureEpisode")):
        under(t, "files/lottery/name/")
        under(t, "files/lottery/text/")  # gacha lines (images) for the moji cut
    # 4) cards and the gacha reveal (the memorial app has no gacha: card art, reveal cuts, opening movies and
    #    gacha-hit voices only exist in the online builds' manifests)
    for r in man_table("pc"):
        cid = r["0"]
        for f in ("lottery", "white", "all_rectangle", "bustup_s", "status_l", "thumbnail_gacha"):
            add(t, f"files/character/lottery/gac_{cid}/{f}.png")
        under(t, f"files/lwf/lotteryLwf/lwf_lottery_ef_{cid}/")
        if r.get("75"):  # gacha-hit voice
            for mk in BYBASE.get("voice_" + r["75"].split(".", 1)[1], []):
                add(t, mk)
    under(t, "files/lwf/uiLwf/lottery/")
    for n in (2, 3, 4):
        add(t, f"files/movie/argo_gacha_op_0{n}.usm")
    # 6) home / town / system voices of the character pages (touch, greetings, alarm, login, costume change,
    #    title calls); many have no text in the memorial data and only exist in an old build's manifest
    vre = re.compile(r"voice_(?:co\d*_(?:[hb]_touch|[dmn]_greet|talk|hold|change)|reaction|sys\d*_town|"
                     r"sys_(?:alarm|login|title|st|fr|pre)|gen)_")
    for k in MAN:
        if k.startswith("files/sound/voice/") and vre.match(os.path.basename(k)):
            add(t, k)
    # 5) event voices come as one zip per episode; fetch the ones no root has unpacked
    for k in MAN:
        if k.startswith("files/sound/voice_episode_zip/") and k.endswith(".zip"):
            if not voices_unpacked(os.path.basename(k)[:-4]):
                add(t, k)
    return t


def voices_unpacked(eid):
    return any(os.path.isdir(os.path.join(r, "files", "sound", "voice_episode", eid)) for r in CFG["asset_roots"])


def unzip_voices():
    """Unpack downloaded event-voice zips into files/sound/voice_episode/<episode>/ (where the player looks)."""
    import zipfile
    out = os.path.realpath(os.path.join(ASSETS, "files", "sound", "voice_episode"))
    done = 0
    for z in sorted(glob.glob(os.path.join(ASSETS, "files", "sound", "voice_episode_zip", "*.zip"))):
        if voices_unpacked(os.path.basename(z)[:-4]):
            continue
        if DRY:
            print("  would unpack", os.path.basename(z))
            continue
        with zipfile.ZipFile(z) as zf:
            for m in zf.namelist():
                dst = os.path.realpath(os.path.join(out, m))
                if not dst.startswith(out + os.sep):  # never write outside the voice folder
                    raise SystemExit(f"unsafe path in {z}: {m}")
            zf.extractall(out)
        done += 1
    return done


def convert_movies():
    """Turn downloaded .usm cutscenes into the .mp4 the player uses (tools/usm.py, needs ffmpeg)."""
    import subprocess
    done = 0
    for usm in glob.glob(os.path.join(ASSETS, "files", "movie", "*.usm")):
        mp4 = usm[:-4] + ".mp4"
        if os.path.exists(mp4) or any(os.path.exists(os.path.join(r, "files", "movie", os.path.basename(mp4))) for r in OTHER_ROOTS):
            continue
        if DRY:
            print("  would convert", os.path.basename(usm))
            continue
        res = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "usm.py"), usm, mp4],
                             capture_output=True, text=True)
        done += res.returncode == 0 and os.path.exists(mp4)
    return done


def in_apk(key):
    """The copy another configured root (the APK, a backup) has of this file, if any."""
    return next((p for p in (os.path.join(r, key) for r in OTHER_ROOTS) if os.path.exists(p)), None)


def elsewhere(key):
    return any(os.path.exists(os.path.join(r, key)) for r in OTHER_ROOTS)


def md5_of(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def unshadow():
    """Remove downloaded copies that differ from the file another configured root (the APK, a backup)
    has — the download root comes first in asset lookup, so they would hide the user's own copy."""
    removed = 0
    for dp, _, fs in os.walk(f"{ASSETS}/files"):
        for fn in fs:
            p = os.path.join(dp, fn)
            apk = in_apk(os.path.relpath(p, f"{ASSETS}"))
            if apk and md5_of(p) != md5_of(apk):
                removed += 1
                if DRY:
                    print("  would remove shadowing copy", os.path.relpath(p, ASSETS))
                else:
                    os.remove(p)
    return removed


def fetch(key):
    info = MAN[key]
    dst = f"{ASSETS}/{key}"
    if in_apk(key) or elsewhere(key):
        return ("have", key)
    if os.path.exists(dst) and os.path.getsize(dst) == info["size"] and md5_of(dst) == info["md5"]:
        return ("skip", key)
    if os.path.exists(dst) and key.startswith("files/ui/single_image/"):
        return ("skip", key)  # another build's copy: same picture, only re-encoded; not worth refetching
    if DRY:
        return ("would", key)
    try:
        req = urllib.request.Request(CDN + info["path"], headers={"User-Agent": "CocosDownloader"})
        data = urllib.request.urlopen(req, timeout=30).read()
        if hashlib.md5(data).hexdigest() != info["md5"]:
            return ("badmd5", key)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + ".tmp"
        open(tmp, "wb").write(data)
        os.replace(tmp, dst)
        return ("ok", key)
    except Exception as e:
        return ("fail:" + str(e)[:40], key)


LEGACY_LOTTERY = {"name": ("name_jp", (960, 240)),  # gacha name plates
                  "text": ("text_jp", (1024, 1024))}  # gacha lines (vertical-text images for the moji cut)


def legacy_plates():
    """Official JP gacha name plates and line images (files/lottery/{name,text}/<card>.png) from the old JP
    online manifests (md5-checked), else the 2017 snapshot (no md5: accept a PNG of the expected size).
    Stored as files/lottery/{name_jp,text_jp}/ so they never mix with the global client's English ones."""
    try:
        cards = json.load(open(f"{CFG['web']}/data/gacha.json", encoding="utf-8"))["cards"]
    except (OSError, ValueError, KeyError):
        print("legacy plates: build web/data first (tools/build_web.py)")
        return

    def one(job):
        kind, cid = job
        sub, (w, h) = LEGACY_LOTTERY[kind]
        rel = f"files/lottery/{sub}/{cid}.png"
        dst = f"{ASSETS}/{rel}"
        if os.path.exists(dst) or elsewhere(rel):
            return kind, "have"
        info = LEGACY_MAN.get(f"files/lottery/{kind}/{cid}.png")
        url = CDN + info["path"] if info else f"{LEGACY}files/lottery/{kind}/{cid}.png"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "CocosDownloader"})
            data = urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError:
            return kind, "absent"  # no old build knew this card
        except Exception:
            return kind, "fail"
        if info and hashlib.md5(data).hexdigest() != info["md5"]:
            return kind, "bad"
        if data[:8] != b"\x89PNG\r\n\x1a\n" or data[16:24] != w.to_bytes(4, "big") + h.to_bytes(4, "big"):
            return kind, "bad"
        if DRY:
            return kind, "would"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst + ".tmp", "wb").write(data)
        os.replace(dst + ".tmp", dst)
        return kind, "ok"

    import collections
    jobs = [(k, c["id"]) for k in LEGACY_LOTTERY for c in cards]
    with ThreadPoolExecutor(max_workers=8) as ex:
        r = collections.Counter(ex.map(one, jobs))
    for k in LEGACY_LOTTERY:
        print(f"legacy JP gacha {k}:", {st: n for (kk, st), n in r.items() if kk == k}, flush=True)


def main():
    print("removed shadowing copies:", unshadow(), flush=True)
    targets = collect()
    total_sz = sum(MAN[k]["size"] for k in targets)
    print(f"target files: {len(targets)}  (~{total_sz/1e6:.0f} MB)", flush=True)
    import collections
    r = collections.Counter()
    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        for status, key in ex.map(fetch, targets):
            r[status.split(":")[0]] += 1
            done += 1
            if done % 500 == 0:
                print(f"  {done}/{len(targets)}  {dict(r)}", flush=True)
    print("DONE", dict(r), flush=True)
    print(f"ok={r['ok']} skip={r['skip']} have={r['have']} badmd5={r['badmd5']} fail={r['fail']} would={r['would']}", flush=True)
    src = lambda k: "own" if k in OWN else "legacy" if k in LEGACY_MAN else "fallback" if k in FALLBACK_KEYS else "backup"
    import collections as _c
    print("targets by manifest:", dict(_c.Counter(src(k) for k in targets)))
    print("unpacked event-voice zips:", unzip_voices(), flush=True)
    print("converted movies:", convert_movies(), flush=True)
    if any(r.get("29") for r in man_table("adventureEpisode")):  # JP memorial data
        legacy_plates()


if __name__ == "__main__":
    main()
