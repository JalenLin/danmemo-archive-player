# DanMemo Archive Player

[中文](README.md) | English | [日本語](README_JP.md)

Relive the stories of *DanMachi: Memoria Freese* (ダンメモ) in a desktop or mobile browser: backgrounds, character portraits and expressions, voices, BGM, sound effects, LWF effects, screen filters and cutscene movies. It also has the memorial app's album, per-character story lists, a portrait viewer and a card gallery.

**This project ships no game assets, no decrypted data and no keys.** Everything is generated from files you obtain yourself, for personal viewing only. Please do not redistribute game assets.

## Features

- **Story** – full index of the main story, events and character stories. Reruns with the same content are merged; episodes already in the album link to it. Events show their original run dates, some with banners.
- **Album** – the memorial app's "Anniversary / Event Story" album: the 48 original events it selected, with banners and run dates. With global data the same selection is applied to the global titles, banners and scripts.
- **Character Stories** – costume stories, character quests and interaction stories per character.
- **Portraits** – portrait and expression viewer.
- **Cards** – card stats and the gacha reveal (with global data it uses the game's official English name plates; for JP data about 342 official plates can be recovered through an old APK's manifest, fetched by `tools/fill_gaps.py`, and the rest are drawn in the rarity's colours; the gacha line is a vertical-text image, also fetched by `fill_gaps.py`: ~690 cards with global data, ~281 with JP data).
- **Movies** – the cutscene movies the stories play (e.g. the seven 6th-anniversary SO12 movies), watchable on their own, each linked to its episode.
- **Others** – story fragments that are not in the index.
- Player: AUTO, SKIP (hold left Ctrl, or toggle), LOG (replay voices), Hide (hide the text box for screenshots: H key or right-click), Settings (text-box colour/opacity, skip delay), continuous playback across a chapter, read marks.
- Interface in English, Japanese or Chinese (picker at the top right; defaults to your browser's language). Story text stays in the language of the data you built from.

## Two ways to set it up

| | Setup A: Japanese memorial app | Setup B: global app-data backup |
|---|---|---|
| Story text | Japanese | **English** (official translation) |
| Voices | Japanese | Japanese |
| Data you need | the JP memorial app `com.danmemo` (free) + assets from the CDN or a backup | a backup of the global app's data folder (`contents/1` … `contents/8`, …) **plus** `libapp.so` from the JP memorial app, for the keys |
| Album | 48 entries | 39 entries (the backup lacks the scripts of the 9 latest events) |

Both use the same tools; only `config.json` differs.

## Requirements

- Python 3.10+; `ffmpeg` (only for converting cutscene movies)
- `pip install pycryptodome pyelftools numpy pillow` (optional: `playwright` for the automated tests, `capstone` for the libapp.so analysis helpers)

```bash
python3 -m venv venv
./venv/bin/pip install pycryptodome pyelftools numpy pillow
```

## Keys (both setups)

The data is encrypted (AES-256-CBC + zlib, strings and numbers with XXTEA). `tools/keys.py` rebuilds the keys from the game's own `libapp.so`; no keys are included here.

**Use the 64-bit `libapp.so` of the Japanese memorial app, version 15.7.2.** The global and Japanese builds use the same keys, so these also decrypt the global data. (The global APK, `com.eu.danmemo`, only contains a 32-bit `libapp.so` with a different layout, which `keys.py` does not support.)

Getting it from a device that has the memorial app installed:

```bash
mkdir -p apk
for p in $(adb shell pm path com.danmemo | sed 's/package://'); do adb pull "$p" apk/; done
mkdir -p x/base x/pack x/lib
unzip -q apk/base.apk -d x/base
unzip -q apk/split_install_pack.apk -d x/pack
unzip -q apk/split_config.arm64_v8a.apk -d x/lib
```

If you have the app as an `.xapk` instead, it is a zip containing the same split APKs (`com.danmemo.apk`, `install_pack.apk`, `config.arm64_v8a.apk`); unzip those the same way.

Then derive the keys, checking them against any `novelCommand*.enc` file:

```bash
./venv/bin/python tools/keys.py x/lib/lib/arm64-v8a/libapp.so path/to/novelCommand751000001.enc
```

This writes `keys.json`. Don't share it.

## Setup B: global app-data backup (English text)

### 1. Lay out the backup

A backup of the global app's data folder looks like this (this is the layout of the community dumps of the EU client):

```
dump/
  contents/1/files/…                       assets
  contents/1/master/divide_enc/*.enc        master tables (431)
  contents/1/master/divide_novel_command_enc/*.enc   story scripts (5,500, English)
  contents/1/manifests/…, project.manifest
  contents/2 … contents/8/files/…           more assets
  voice_root/files/sound/voice_episode/…    event voices (already unpacked)
  single_image_root/files/ui/single_image/… story backgrounds and CGs
  area_atlas_root/…                         quest maps (not needed)
```

If yours came as `contents.part1.rar` … `part6.rar`, extract them first (`unrar x contents.part1.rar`).

### 2. config.json

```json
{
  "libapp": "x/lib/lib/arm64-v8a/libapp.so",
  "novel_dirs":  ["dump/contents/1/master/divide_novel_command_enc"],
  "master_dirs": ["dump/contents/1/master/divide_enc"],
  "asset_roots": [
    "dump/contents/1", "dump/contents/2", "dump/contents/3", "dump/contents/4",
    "dump/contents/5", "dump/contents/6", "dump/contents/7", "dump/contents/8",
    "dump/voice_root", "dump/single_image_root"
  ]
}
```

Paths are relative to the project root. Earlier asset roots win when a file exists in several of them.
To keep several setups side by side, put each in its own file and select it with `DANMEMO_CONFIG=path/to/config.json` (every tool honours it; you can also set `"dec"` and `"web"` output folders per config).

### 3. Movies

Cutscenes are CRI USM files; convert them once:

```bash
for f in dump/contents/*/files/movie/*.usm; do ./venv/bin/python tools/usm.py "$f" "${f%.usm}.mp4"; done
```

### 4. Decrypt, build, serve

```bash
./venv/bin/python tools/decrypt_all.py
./venv/bin/python tools/build_web.py
./venv/bin/python tools/serve.py          # open http://localhost:8080/
```

Optional – fetch what the backup is missing (including the official gacha name plates, which the community dumps don't contain). `tools/fill_gaps.py` reads the manifests inside your backup and skips everything any configured asset root already has, downloading only the rest into `assets/` (add `"assets"` as the first entry of `asset_roots`). If you also run `tools/fetch_manifests.py` (it uses the JP `libapp.so` from `config.json`), it can fill some gaps from the Japanese memorial app's file list as well. Then run `tools/build_web.py` again.

```bash
./venv/bin/python tools/fill_gaps.py --dry   # list what it would download
./venv/bin/python tools/fill_gaps.py
```

`tools/serve.py 8080 0.0.0.0` makes it reachable from other devices on your network.

### What to expect

We verified this path with the EU dump's layout and data, with no Japanese files configured: 5,931 files decrypt with 0 errors; 5,500 English scripts (5,261 in the story index), 39 album entries, 26 character pages and 784 cards build; 40 randomly picked stories played through without errors, with English text and Japanese voices.

Known gaps and limitations:

- **Album: 39 of 48 entries**. The album is the memorial app's selection of original events; the tools apply the same selection to the global data, but the backup has no scripts for the 9 latest ones (Orgion Saga I–III, Valhalla Panic, Overture of the Sword and Spear, Knossos War, Memoria Freese, A Twilight Dream, the S4 Calamity Arc side stories).
- **Some missing images**: about 2,175 image references in the English scripts point to files the global backup doesn't contain, and roughly 1,000 references (voices, images, sound effects) are missing from every known source. The player skips them.

## Setup A: Japanese memorial app

1. Get the APK and keys as above.
2. `cp config.example.json config.json` and adjust the paths.
3. Assets, either:
   - from the CDN:
     ```bash
     ./venv/bin/python tools/fetch_manifests.py
     ./venv/bin/python tools/download.py
     cd assets/files/sound && mkdir -p voice_episode && for z in voice_episode_zip/*.zip; do unzip -q -n "$z" -d voice_episode; done; cd -
     ```
   - or from your own app-data backup: add each folder that contains `files/` to `asset_roots`.
4. Convert movies (`tools/usm.py`, as above), then:
   ```bash
   ./venv/bin/python tools/decrypt_all.py
   ./venv/bin/python tools/build_web.py
   ./venv/bin/python tools/legacy_manifests.py old.apk   # optional: with a JP APK of 8.x or older, fetch that build's online manifest (JP banners, name plates, …)
   ./venv/bin/python tools/fill_gaps.py   # optional: fetch assets the stories use but the memorial manifests omit; then run build_web.py again
   ./venv/bin/python tools/serve.py
   ```

Optionally, add the global backup's scripts as a translation source in `config.json` (`"translations": {"en": {"novel_dirs": [...], "master_dirs": [...]}}`) and run `tools/decrypt_all.py --lang en` (→ `dec_en/`).

## Controls

- Click, Space or Enter: next line
- Hold left Ctrl: fast-forward while held; SKIP toggles it
- AUTO: auto-advance (waits for the voice)
- LOG: backlog (press again or Esc to close; replay voices)
- Hide / H / right-click: hide the text box; click to bring it back
- Settings: text-box colour and opacity, skip delay
- Esc: back to the index
- Read marks and settings are stored in your browser

## Project layout

```
tools/keys.py            derive keys from libapp.so
tools/dmcrypto.py        AES-256-CBC + zlib + XXTEA
tools/fbdump.py          schema-less FlatBuffers reader (incl. encrypted int32/int64 scalars)
tools/decrypt_all.py     decrypt everything → dec/ (--lang en → dec_en/)
tools/build_web.py       build web/data/ (story index, album, per-story JSON, galleries)
tools/fetch_manifests.py fetch the CDN asset manifests
tools/download.py        download assets from the CDN (resumable, md5-checked)
tools/legacy_manifests.py read the remote manifest URL from an old (pre-2020, pre-md5 CDN) JP APK → cdn/legacy/, so fill_gaps.py can fetch Japanese originals
tools/fill_gaps.py       fetch assets the stories use but the memorial manifests omit
tools/config.py          loads config.json (or the file named by DANMEMO_CONFIG)
tools/cardstat.py        card stat calculator (reverse-engineered from the memorial app's character screen)
tools/download_extra.py  download extra assets listed in a manifest-style JSON
tools/gacha_voice_alias.json  gacha voices that reuse story voice files (file names only)
tools/usm.py             CRI USM → MP4
tools/gachanames.py      gacha name plates (called by build_web.py)
tools/serve.py           local server with HTTP Range support
web/js/i18n.js           interface strings (Japanese keys → English / Chinese) and date formats
tools/smoke.py, shot.py  player tests / screenshots (Playwright; set DANMEMO_URL)
tools/gdrive_ls.py, gdrive_get.py   list / download a public Google Drive folder
tools/wayback_get.py     download JP notice art and pages known to the Wayback Machine (research)
tools/elfre.py, reloc.py, novelcmd_map.py   libapp.so analysis helpers
web/                     the player (plain HTML/JS, no build step)
docs/PROCESS.md          full analysis notes (Chinese)
```

## License

- This project's code: not yet decided
- `web/vendor/lwf.js`: GREE LWF, zlib License (see `web/vendor/LWF-LICENSE.txt`)
- Game content is copyright of its respective owners
