# DanMemo Archive Player

中文 | [English](README_EN.md) | [日本語](README_JP.md)

在電腦或手機瀏覽器上重溫《ダンまち〜メモリア・フレーゼ〜》（ダンメモ）的劇情：背景、立繪表情、語音、BGM、音效、LWF 特效、濾鏡、過場影片都能播放，另外有紀念版相簿、角色劇情、角色立繪和卡片鑑賞。

**本專案不含任何遊戲資源、解密後的資料或金鑰。** 所有素材都要由使用者用自己取得的檔案產生，只供個人觀看，請勿散布遊戲素材。

> 只有國際版 App 資料備份（英文劇情）的使用者，請看 [README_EN.md](README_EN.md) 的「Setup B」。

## 功能

- **ストーリー**：主線、活動、角色劇情的完整目錄。同內容的復刻合併成一筆；紀念版相簿已收錄的篇目會連到相簿。活動顯示開催期間，部分有橫幅。
- **アルバム**：照紀念版 App 的「周年ストーリー／イベントストーリー」重現（48 篇，官方橫幅與開催期間）。
- **キャラストーリー（角色劇情）**：每個角色的服裝劇情、キャラクエ、ふれあい。
- **立ち絵（角色立繪）**：立繪與表情鑑賞。
- **カード（卡片）**：卡片能力值與抽卡演出（國際版資料用官方英文名牌；日版用舊版 APK 的清單可找回約 342 張官方名牌，由 `fill_gaps.py` 下載，其餘依稀有度配色自動產生；抽卡台詞是直書圖片，同樣由 `fill_gaps.py` 取得：日版約 281 張、國際版約 690 張）。
- **ムービー（影片）**：劇情裡的過場影片（例如 6 周年 SO12 的 7 支），可以單獨觀看，並連到出處劇情。
- **その他（其他）**：不在目錄裡的劇情片段。
- 播放器：AUTO、SKIP（按住左 Ctrl 或切換）、LOG（可重播語音）、隱藏（隱藏對話框截圖用，H 鍵或右鍵）、設定（文字框顏色／不透明度、SKIP 間隔）、同一章節連續播放、已讀紀錄。
- 介面語言：中文／English／日本語，右上角切換，預設跟著瀏覽器語言。劇情文字維持建置時所用資料的語言。

## 需要準備

- Python 3.10 以上；`ffmpeg`（只有轉換過場影片時需要）
- 日文版紀念 App（オフライン版，`com.danmemo`）的 APK，從**自己的手機**用 adb 取出
- 素材，任選一種（可以混用）：
  - 用 `tools/download.py` 從遊戲的 CDN 下載（約 11 GB）
  - 自己的 App 資料備份資料夾（`contents/1` … `contents/8` 這種結構）
- （選用）國際版的 App 資料備份：補足紀念版沒有收錄的素材，或當作第二階段翻譯的對照

## 安裝

```bash
python3 -m venv venv
./venv/bin/pip install pycryptodome pyelftools numpy pillow
# 選用：playwright（自動測試）、capstone（分析 libapp.so 的工具）
```

## 步驟

### 1. 從手機取出 APK

在手機開啟 USB 偵錯，然後：

```bash
mkdir -p apk
for p in $(adb shell pm path com.danmemo | sed 's/package://'); do adb pull "$p" apk/; done
mkdir -p x/base x/pack x/lib
unzip -q apk/base.apk -d x/base
unzip -q apk/split_install_pack.apk -d x/pack
unzip -q apk/split_config.arm64_v8a.apk -d x/lib
```

### 2. 從自己的 libapp.so 產生金鑰

```bash
./venv/bin/python tools/keys.py x/lib/lib/arm64-v8a/libapp.so \
    x/pack/assets/master/divide_novel_command_enc/novelCommand751000001.enc
```

會產生 `keys.json`（不要分享這個檔案）。目前支援的是紀念版 15.7.2 的 `libapp.so`。

### 3. 設定

```bash
cp config.example.json config.json   # 依實際路徑修改
```

- `asset_roots`：素材根目錄，**越前面越優先**（每個根目錄底下是 `files/...`）
- `novel_dirs`、`master_dirs`：`.enc` 檔所在的資料夾
- `translations.en`（選用）：國際版的劇情與主資料，用於第二階段翻譯
- 想同時保留多套設定：各寫一個設定檔，用環境變數 `DANMEMO_CONFIG=路徑` 指定（每支工具都支援，也可以各自設定 `dec`、`web` 輸出位置）

### 4. 準備素材

```bash
# 方法 A：從 CDN 下載清單和素材
./venv/bin/python tools/fetch_manifests.py
./venv/bin/python tools/download.py
# 活動語音 zip 解壓
cd assets/files/sound && mkdir -p voice_episode && for z in voice_episode_zip/*.zip; do unzip -q -n "$z" -d voice_episode; done; cd -
```

方法 B：已經有 App 資料備份的話，把每個含 `files/` 的資料夾加進 `config.json` 的 `asset_roots`。

```bash
# 過場影片 USM → MP4（兩種方法都需要）
for f in assets/files/movie/*.usm; do ./venv/bin/python tools/usm.py "$f" "${f%.usm}.mp4"; done
```

### 5. 解密、建置、啟動

```bash
./venv/bin/python tools/decrypt_all.py
./venv/bin/python tools/build_web.py
./venv/bin/python tools/legacy_manifests.py 舊版.apk  # 選用：有 8.x 以前的日版 APK 時，取得當時的線上清單（日文橫幅、名牌等）
./venv/bin/python tools/fill_gaps.py      # 選用：補下載紀念版清單沒有、但劇情用得到的素材，之後再跑一次 build_web.py
./venv/bin/python tools/serve.py          # 開啟 http://localhost:8080/
```

要讓同一個網路的手機觀看：`tools/serve.py 8080 0.0.0.0`，再用電腦的區網 IP 連線。

## 操作

- 點擊畫面、空白鍵或 Enter：下一句
- 按住左 Ctrl：快轉，放開就停；SKIP 按鈕切換快轉
- AUTO：自動播放（等語音結束）
- LOG：對話紀錄（再按一次或 Esc 關閉，可重播語音）
- 非表示／H／右鍵：隱藏對話框；點一下畫面恢復
- 設定：文字框顏色與不透明度、SKIP 速度
- Esc：回到目錄
- 已讀紀錄和設定存在瀏覽器裡

## 專案結構

```
tools/keys.py           從 libapp.so 推導金鑰
tools/dmcrypto.py       AES-256-CBC + zlib + XXTEA 解密
tools/fbdump.py         不需要 schema 的 FlatBuffers 解析器（含加密數值 int32／int64）
tools/decrypt_all.py    批次解密 → dec/（--lang en 解國際版 → dec_en/）
tools/build_web.py      產生 web/data/（劇情目錄、相簿、每段劇情、鑑賞資料）
tools/fetch_manifests.py 抓 CDN 的素材清單
tools/download.py       從 CDN 下載素材（續傳、MD5 驗證）
tools/legacy_manifests.py 從舊版（2019 年以前、舊制 CDN）APK 讀出遠端清單 → cdn/legacy/，供 fill_gaps.py 補日文原版素材
tools/fill_gaps.py      補下載劇情用到但手上沒有的素材（日版清單優先，國際版／備份內附清單補缺；已設定的素材目錄有的就不下載）
tools/config.py         讀取 config.json（或 DANMEMO_CONFIG 指定的設定檔）
tools/cardstat.py       卡片能力值計算（對照紀念版「キャラ詳細」畫面反推）
tools/download_extra.py 依清單格式的 JSON 下載額外素材
tools/gacha_voice_alias.json  抽卡語音沿用劇情語音的對照（只有檔名）
tools/usm.py            CRI USM → MP4
tools/gachanames.py     抽卡演出的名牌圖（build_web.py 會呼叫）
tools/serve.py          本機伺服器（支援 Range）
web/js/i18n.js          介面文字（日文為鍵 → 英文／中文）與日期格式
tools/smoke.py          播放器自動測試（Playwright；DANMEMO_URL 指定網址）
tools/shot.py           播放器截圖（同上）
tools/gdrive_ls.py / gdrive_get.py  列出／下載公開的 Google Drive 資料夾
tools/wayback_get.py    下載 Wayback Machine 收錄的日版公告圖與公告頁（研究用）
tools/elfre.py / reloc.py / novelcmd_map.py  分析 libapp.so 的小工具
web/                    播放器（純 HTML/JS，不需要建置）
docs/PROCESS.md         完整的分析與製作紀錄
README_EN.md / README_JP.md  英文／日文說明
```

## 授權

- 本專案程式：自行決定（尚未指定）
- `web/vendor/lwf.js`：GREE LWF，zlib License（見 `web/vendor/LWF-LICENSE.txt`）
- 遊戲內容的著作權屬於原權利人
