# DanMemo Archive Player

[中文](README.md) | [English](README_EN.md) | 日本語

『ダンまち〜メモリア・フレーゼ〜』（ダンメモ）のストーリーを、PC やスマートフォンのブラウザで振り返るためのツールです。背景、立ち絵と表情、ボイス、BGM、効果音、LWF エフェクト、画面フィルター、ムービーを再生でき、メモリアルアプリのアルバム（開催期間のあるイベントを追加）、キャラ別ストーリーとボイス、立ち絵ビューア、ガチャ演出つきのカードギャラリー、ムービーページもあります。

**このプロジェクトにはゲームのリソース、復号済みデータ、鍵は一切含まれていません。** すべてご自身で入手したファイルから生成し、個人的な閲覧にのみ使用してください。ゲーム素材の再配布はおやめください。

## 機能

- **ストーリー**：メインストーリーと、開催期間のないシナリオ（栄光挑戦、チュートリアルなど）。開催期間のあるイベントはすべて「アルバム」にあります。内容が同じ復刻は 1 件にまとめます。イベントには開催期間を表示し、一部はバナー付きです。
- **アルバム**：メモリアルアプリの「周年ストーリー／イベントストーリー」を再現（48 件、公式バナーと開催期間付き）。加えて、アルバム未収録で開催期間のある「その他のイベント」「降臨イベント」と、内容が初回と異なる「復刻イベント」のタブ。
- **キャラストーリー**：キャラクターごとの衣装ストーリー、キャラクエ、ふれあい、プロフィールとボイス（ログイン、挨拶、タッチ、交流、街、アラーム、衣装チェンジ、システム。日本版 約 8,300 件）。
- **立ち絵**：立ち絵・表情ビューア。
- **カード**：カードのステータスとガチャ演出（海外版データでは公式の英語プレート。日本版は旧版 APK のマニフェストから約 342 枚の公式プレートを `fill_gaps.py` で取得、それ以外はレアリティ別の配色で自動生成。ガチャ台詞は縦書きの画像で、同じく `fill_gaps.py` で取得：日本版 約 281 枚、海外版 約 690 枚）。
- **ムービー**：ストーリー中のムービー（6 周年 SO12 の 7 本など）を単独で視聴でき、該当話へ移動できます。
- **その他**：一覧に含まれないストーリー断片。次回予告・拠点ノベルはイベントに対応するものをそのイベントの先頭に、残りを「拠点ノベル・予告」に日付順で、TV アニメ放送前のものは期ごと（2〜4 期）に表示。
- プレイヤー：AUTO、SKIP（左 Ctrl 長押し、または切り替え）、LOG（ボイス再生可）、非表示（スクリーンショット用にテキストボックスを隠す。H キーまたは右クリック）、設定（テキストボックスの色・不透明度、SKIP 間隔）、章ごとの連続再生、既読管理。
- 表示言語：日本語／English／中文を右上で切り替え（初期値はブラウザの言語）。ストーリー本文はビルドに使ったデータの言語のままです。

## 必要なもの

- Python 3.10 以上、`ffmpeg`（ムービー変換時のみ）
- 日本版メモリアルアプリ（オフライン版、`com.danmemo`）の APK。**ご自身の端末**から adb で取り出してください
- 素材（どちらでも、併用も可）：
  - `tools/download.py` でゲームの CDN からダウンロード（約 11 GB）
  - ご自身のアプリデータのバックアップ（`contents/1` … `contents/8` の構成）
- **推奨**：8.x 以前（2019 年）の日本版 APK。メモリアルアプリにないカード画像、ガチャ演出、日本語ネームプレートと台詞、イベントバナーはこのマニフェストから取得します（手順 5）
- （任意）海外版アプリデータのバックアップ：メモリアルアプリにも旧版にもない素材の補完（英語版になります）、または翻訳の参照用

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

`keys.json` が作成されます（共有しないでください）。対応しているのはメモリアルアプリ 15.7.2 の `libapp.so` と、グローバル版 2023-12-22 の APK（`com.eu.danmemo`、コミュニティのデータバックアップと一緒に共有されているもの。`.apk` をそのまま渡せば中の 32bit `libapp.so` を使います）の 2 つで、鍵は共通です。

### 3. 設定

```bash
cp config.example.json config.json   # パスを環境に合わせて編集
```

- `asset_roots`：素材のルートフォルダ。**先に書いたものが優先**されます（各ルートの下は `files/...`）
- `novel_dirs`、`master_dirs`：`.enc` ファイルのあるフォルダ
- `translations.en`（任意）：海外版のストーリーとマスターデータ（翻訳用）
- `manifests`、`legacy_manifests`：この設定自身の素材マニフェスト（既定は `cdn/` のメモリアルアプリ版と `cdn/legacy/`）。ここに書いたものだけを使い、プロジェクト内の他のマニフェストは読みません
- `fallback_manifests`（任意、既定は空）：他地域（海外版など）のマニフェストで不足分を補います。補った画像はその地域の言語の場合があります
- 複数の設定を使い分ける場合：設定ファイルごとに環境変数 `DANMEMO_CONFIG=パス` で指定（全ツール対応。`dec`、`web` の出力先も個別に設定可能）

### 4. 素材の準備

```bash
# 方法 A：CDN からマニフェストと素材をダウンロード
./venv/bin/python tools/fetch_manifests.py
./venv/bin/python tools/download.py
# イベントボイスの zip を展開（手順 5 の fill_gaps.py も自動で展開します）
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
./venv/bin/python tools/legacy_manifests.py 旧版.apk  # 推奨：8.x 以前（2019 年）の日本版 APK、下記参照
./venv/bin/python tools/fill_gaps.py
./venv/bin/python tools/build_web.py
./venv/bin/python tools/serve.py          # http://localhost:8080/ を開く
```

メモリアルアプリにはガチャがなく、マニフェストにもストーリーで使う多くのファイルが含まれていません。それ以外の日本語素材は旧オンライン版から取得します：`legacy_manifests.py` が 8.x の APK に書かれたマニフェスト URL を読み（これらは現在も取得可能）、`fill_gaps.py` がそこからカード画像、ガチャ演出とボイス、日本語ネームプレートと台詞、イベントバナー、ストーリー素材を取得します（ムービーは自動で MP4 に変換、イベントボイスの zip も自動で展開）。ゼロからの実測（2026-10）：

| | メモリアルアプリのみ | + 8.2.0 APK |
|---|---|---|
| 素材がすべて揃うシナリオ | 4,480 / 11,462 | 10,531 |
| ストーリー一覧のバナー | 0 | 160 |
| カード画像／ガチャボイスのあるカード | 8／42 | 297／281 |
| 公式ネームプレート／ガチャ台詞 | 108／75（2017 年のスナップショット） | 342／281 |
| ガチャ演出（カット、オープニング） | なし | あり |

2019 年 9 月以降のカードとイベントは海外版データにしかありません。最大限そろえる（混ぜる）方法は 2 つで、補った画像は英語になります：
- `config.json` の `fallback_manifests` に海外版のマニフェスト（海外版バックアップの `contents/*/project.manifest` など）を書くと、`fill_gaps.py` が不足分を CDN から取得
- または海外版バックアップのフォルダを `asset_roots` に（日本版の後ろに）追加すると、ビルド時にそのまま使用

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
tools/fill_gaps.py       ストーリーで使うが手元にない素材を追加取得（この設定自身のマニフェストのみ：config の manifests・legacy_manifests とバックアップ同梱のもの。他地域のマニフェストは fallback_manifests に書いた場合だけ使用。設定済みの素材フォルダにあるものは取得しない）
tools/config.py          config.json（または DANMEMO_CONFIG の設定ファイル）の読み込み
tools/cardstat.py        カードのステータス計算（メモリアルアプリの「キャラ詳細」から逆算）
tools/download_extra.py  マニフェスト形式の JSON に列挙した素材を追加取得
tools/usm.py             CRI USM → MP4
tools/gachanames.py      ガチャ演出のネームプレート（build_web.py から呼ばれる）
tools/serve.py           ローカルサーバー（Range 対応）
web/js/i18n.js           画面の文言（日本語をキーに英語／中国語）と日付形式
tools/smoke.py           プレイヤーのテスト：早送りでシナリオを再生し、停止・コマンドエラー・素材の読み込み失敗を報告（`smoke.py all --workers 10` で全件。Playwright、DANMEMO_URL で URL 指定）
tools/vidcompare.py      原作の録画と比較：一行ずつスクリーンショットを撮り、動画と対応付けて差の大きい行を一覧にする（ffmpeg・Playwright が必要）
tools/shot.py            スクリーンショット（同上）
tools/gdrive_ls.py, gdrive_get.py   公開 Google Drive フォルダの一覧／ダウンロード
tools/wayback_get.py     Wayback Machine にある日本版お知らせ画像・ページの取得（調査用）
tools/elfre.py, reloc.py, novelcmd_map.py   libapp.so 解析用の小ツール
web/                     プレイヤー（HTML/JS のみ、ビルド不要）
docs/PROCESS.md          解析と制作の記録（中国語）
```

## ライセンス

- 本プロジェクトのコード：[MIT License](LICENSE)
- `web/vendor/lwf.js`：GREE LWF、zlib License（`web/vendor/LWF-LICENSE.txt` 参照）
- ゲーム内容の著作権は各権利者に帰属します
