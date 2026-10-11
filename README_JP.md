# DanMemo Archive Player

[中文](README.md) | [English](README_EN.md) | 日本語

『ダンまち〜メモリア・フレーゼ〜』（ダンメモ）のストーリーを、PC やスマートフォンのブラウザで振り返るためのツールです。背景、立ち絵と表情、ボイス、BGM、効果音、LWF エフェクト、画面フィルター、ムービーを再生でき、メモリアルアプリのアルバム、キャラ別ストーリー、立ち絵ビューア、カードギャラリーもあります。

**このプロジェクトにはゲームのリソース、復号済みデータ、鍵は一切含まれていません。** すべてご自身で入手したファイルから生成し、個人的な閲覧にのみ使用してください。ゲーム素材の再配布はおやめください。

## 機能

- **ストーリー**：メイン、イベント、キャラストーリーの一覧。内容が同じ復刻は 1 件にまとめ、アルバム収録済みのエピソードはアルバムへリンクします。イベントには開催期間を表示し、一部はバナー付きです。
- **アルバム**：メモリアルアプリの「周年ストーリー／イベントストーリー」を再現（48 件、公式バナーと開催期間付き）。
- **キャラストーリー**：キャラクターごとの衣装ストーリー、キャラクエ、ふれあい。
- **立ち絵**：立ち絵・表情ビューア。
- **カード**：カードのステータスとガチャ演出（海外版データでは公式の英語プレート。日本版は旧版 APK のマニフェストから約 342 枚の公式プレートを `fill_gaps.py` で取得、それ以外はレアリティ別の配色で自動生成。ガチャ台詞は縦書きの画像で、同じく `fill_gaps.py` で取得：日本版 約 281 枚、海外版 約 690 枚）。
- **ムービー**：ストーリー中のムービー（6 周年 SO12 の 7 本など）を単独で視聴でき、該当話へ移動できます。
- **その他**：一覧に含まれないストーリー断片。
- プレイヤー：AUTO、SKIP（左 Ctrl 長押し、または切り替え）、LOG（ボイス再生可）、非表示（スクリーンショット用にテキストボックスを隠す。H キーまたは右クリック）、設定（テキストボックスの色・不透明度、SKIP 間隔）、章ごとの連続再生、既読管理。
- 表示言語：日本語／English／中文を右上で切り替え（初期値はブラウザの言語）。ストーリー本文はビルドに使ったデータの言語のままです。

## 必要なもの

- Python 3.10 以上、`ffmpeg`（ムービー変換時のみ）
- 日本版メモリアルアプリ（オフライン版、`com.danmemo`）の APK。**ご自身の端末**から adb で取り出してください
- 素材（どちらでも、併用も可）：
  - `tools/download.py` でゲームの CDN からダウンロード（約 11 GB）
  - ご自身のアプリデータのバックアップ（`contents/1` … `contents/8` の構成）
- （任意）海外版アプリデータのバックアップ：メモリアルアプリに収録されていない素材の補完、または翻訳の参照用

```bash
python3 -m venv venv
./venv/bin/pip install pycryptodome pyelftools numpy pillow
# 任意：playwright（自動テスト）、capstone（libapp.so 解析ツール）
```

## 手順

### 1. 端末から APK を取り出す

端末の USB デバッグを有効にして：

```bash
mkdir -p apk
for p in $(adb shell pm path com.danmemo | sed 's/package://'); do adb pull "$p" apk/; done
mkdir -p x/base x/pack x/lib
unzip -q apk/base.apk -d x/base
unzip -q apk/split_install_pack.apk -d x/pack
unzip -q apk/split_config.arm64_v8a.apk -d x/lib
```

### 2. libapp.so から鍵を生成

```bash
./venv/bin/python tools/keys.py x/lib/lib/arm64-v8a/libapp.so \
    x/pack/assets/master/divide_novel_command_enc/novelCommand751000001.enc
```

`keys.json` が作成されます（共有しないでください）。対応しているのはメモリアルアプリ 15.7.2 の `libapp.so` です。

### 3. 設定

```bash
cp config.example.json config.json   # パスを環境に合わせて編集
```

- `asset_roots`：素材のルートフォルダ。**先に書いたものが優先**されます（各ルートの下は `files/...`）
- `novel_dirs`、`master_dirs`：`.enc` ファイルのあるフォルダ
- `translations.en`（任意）：海外版のストーリーとマスターデータ（翻訳用）
- 複数の設定を使い分ける場合：設定ファイルごとに環境変数 `DANMEMO_CONFIG=パス` で指定（全ツール対応。`dec`、`web` の出力先も個別に設定可能）

### 4. 素材の準備

```bash
# 方法 A：CDN からマニフェストと素材をダウンロード
./venv/bin/python tools/fetch_manifests.py
./venv/bin/python tools/download.py
# イベントボイスの zip を展開
cd assets/files/sound && mkdir -p voice_episode && for z in voice_episode_zip/*.zip; do unzip -q -n "$z" -d voice_episode; done; cd -
```

方法 B：アプリデータのバックアップがある場合は、`files/` を含む各フォルダを `config.json` の `asset_roots` に追加します。

```bash
# ムービー USM → MP4（どちらの方法でも必要）
for f in assets/files/movie/*.usm; do ./venv/bin/python tools/usm.py "$f" "${f%.usm}.mp4"; done
```

### 5. 復号、ビルド、起動

```bash
./venv/bin/python tools/decrypt_all.py
./venv/bin/python tools/build_web.py
./venv/bin/python tools/legacy_manifests.py 旧版.apk  # 任意：8.x 以前の日本版 APK があれば当時のオンライン版マニフェストを取得（日本語バナー、ネームプレートなど）
./venv/bin/python tools/fill_gaps.py      # 任意：メモリアルアプリのマニフェストにないがストーリーで使う素材を追加ダウンロード。その後 build_web.py を再実行
./venv/bin/python tools/serve.py          # http://localhost:8080/ を開く
```

同じネットワークのスマートフォンから見る場合は `tools/serve.py 8080 0.0.0.0` で起動し、PC の LAN 内 IP にアクセスします。

海外版のバックアップだけで（英語テキストで）構築する方法は [README_EN.md](README_EN.md) の「Setup B」を参照してください。

## 操作

- クリック、Space、Enter：次へ
- 左 Ctrl 長押し：早送り（離すと停止）、SKIP ボタンで切り替え
- AUTO：自動再生（ボイスの終了を待つ）
- LOG：バックログ（もう一度押すか Esc で閉じる、ボイス再生可）
- 非表示／H／右クリック：テキストボックスを隠す（画面クリックで戻る）
- 設定：テキストボックスの色と不透明度、SKIP 速度
- Esc：一覧に戻る
- 既読と設定はブラウザに保存されます

## 構成

```
tools/keys.py            libapp.so から鍵を導出
tools/dmcrypto.py        AES-256-CBC + zlib + XXTEA の復号
tools/fbdump.py          スキーマ不要の FlatBuffers リーダー（暗号化 int32／int64 対応）
tools/decrypt_all.py     一括復号 → dec/（--lang en で海外版 → dec_en/）
tools/build_web.py       web/data/ を生成（ストーリー一覧、アルバム、各ストーリー、ギャラリー）
tools/fetch_manifests.py CDN のマニフェストを取得
tools/download.py        CDN から素材をダウンロード（再開可、MD5 検証）
tools/legacy_manifests.py 旧版（2019 年以前の旧方式 CDN）APK からリモートマニフェストを取得 → cdn/legacy/（fill_gaps.py が日本語版素材の補完に使用）
tools/fill_gaps.py       ストーリーで使うが手元にない素材を追加取得（日本版マニフェスト優先、海外版／バックアップ同梱のマニフェストで補完。設定済みの素材フォルダにあるものは取得しない）
tools/config.py          config.json（または DANMEMO_CONFIG の設定ファイル）の読み込み
tools/cardstat.py        カードのステータス計算（メモリアルアプリの「キャラ詳細」から逆算）
tools/download_extra.py  マニフェスト形式の JSON に列挙した素材を追加取得
tools/gacha_voice_alias.json  ガチャボイスがストーリーボイスを流用している対応表（ファイル名のみ）
tools/usm.py             CRI USM → MP4
tools/gachanames.py      ガチャ演出のネームプレート（build_web.py から呼ばれる）
tools/serve.py           ローカルサーバー（Range 対応）
web/js/i18n.js           画面の文言（日本語をキーに英語／中国語）と日付形式
tools/smoke.py, shot.py  プレイヤーのテスト／スクリーンショット（Playwright、DANMEMO_URL で URL 指定）
tools/gdrive_ls.py, gdrive_get.py   公開 Google Drive フォルダの一覧／ダウンロード
tools/wayback_get.py     Wayback Machine にある日本版お知らせ画像・ページの取得（調査用）
tools/elfre.py, reloc.py, novelcmd_map.py   libapp.so 解析用の小ツール
web/                     プレイヤー（HTML/JS のみ、ビルド不要）
docs/PROCESS.md          解析と制作の記録（中国語）
```

## ライセンス

- 本プロジェクトのコード：未定
- `web/vendor/lwf.js`：GREE LWF、zlib License（`web/vendor/LWF-LICENSE.txt` 参照）
- ゲーム内容の著作権は各権利者に帰属します
