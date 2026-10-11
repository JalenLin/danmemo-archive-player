# ダンメモ オフライン版 劇情取出紀錄

目標：
1. 第一階段：在電腦上觀看劇情（網頁或程式，包含立繪、背景、演出）。
2. 第二階段：翻譯（之後另外處理）。

> 取出的內容僅供個人觀看，不散布。

## 環境

| 項目 | 內容 |
|---|---|
| 手機 | Pixel 10 Pro（Android 17） |
| App | `com.danmemo`，versionName 15.7.2（2024/9/24 上架的オフライン版） |
| 電腦 | Linux，Python 3.12 venv（`venv/`：capstone、pyelftools、pycryptodome、numpy） |
| adb | Google platform-tools，放在 `platform-tools/` |

## 1. 連接手機

1. 手機開啟開發人員選項 → USB 偵錯。
2. Linux 加 udev 規則，否則 adb 顯示 `no permissions`：
   ```
   echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0660", GROUP="plugdev"' | sudo tee /etc/udev/rules.d/51-android.rules
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
3. 重插 USB，手機上允許偵錯，`platform-tools/adb devices -l` 確認狀態是 `device`。

## 2. 取出 APK

`/sdcard/Android/data/com.danmemo` 不存在，所有資源都打包在 APK（Play Asset Delivery 的 install-time pack）裡。

```
for p in $(adb shell pm path com.danmemo | sed 's/package://'); do adb pull "$p" apk/; done
```

取得 7 個檔案，重要的是：
- `base.apk`（140 MB）：`assets/common/master/divide_enc/*.enc`（主資料）、`assets/lua/*.enc`
- `split_install_pack.apk`（370 MB）：`assets/master/divide_novel_command_enc/novelCommand*.enc`（**劇情腳本，11,462 個**）、`assets/files/`（立繪、背景、UI、音效）
- `split_config.arm64_v8a.apk`：`lib/arm64-v8a/libapp.so`（遊戲本體，37 MB）

解壓到 `x/base`、`x/pack`、`x/lib`。

## 3. 分析遊戲本體

- 引擎：**cocos2d-x（C++）**，遊戲程式命名空間 `toybox`、底層函式庫 `wfs`，音訊用 CRI ADX2，動畫用 LWF 和 Spine。
- `.enc` 檔大小都是 16 的倍數，推測是 AES。
- `libapp.so` 裡找到的關鍵字串：
  - `static std::string wfs::crypto::Aes::decrypt(const unsigned char *, size_t, const std::string &key, const std::string &iv, bool, bool)`
  - `static std::string flatbuffers::Xxtea::DecryptScalar(const void *, size_t)`（推測解密後是 FlatBuffers，部分欄位另外用 XXTEA 加密）
  - `master/divide_{}/{}{}`、`master/divide_bundled_{}/{}{}`

工具：`tools/elfre.py`（用 numpy 掃描 ADRP/ADD 字串參照、BL 呼叫者，用 capstone 反組譯）。

### 函式位置（libapp.so，15.7.2）

| 位址 | 內容 |
|---|---|
| `0x13c55ec` | `wfs::crypto::Aes::decrypt(ptr, len, key, iv, bool, bool)` |
| `0x13c59a4` | 包裝：`Aes::decrypt(std::string data, key, iv, bool, bool)` |
| `0xc29348` | MasterData 載入函式：組出金鑰 → 呼叫 `0x13c59a4` → 交給 `0xc3145c` 解析 |

### AES 金鑰

金鑰沒有以明文存放，執行時用查表還原（`0xc29410` 附近）：

```
S = libapp.so @ 0x1bbd0ec（32 bytes）
T = libapp.so @ 0x1bbd20c（256 bytes）
key[i] = T[S[i] ^ 0xCB] ^ 0xD7    (i = 0..31)
```

結果是 32 bytes 的 AES-256 金鑰（可以用上面的公式從 libapp.so 重新算出來）。

驗證：AES-256-CBC 解密後，除了第一個 16-byte 區塊，其他內容都一致，結尾的 PKCS#7 padding 正確 → 金鑰正確。

### AES IV

- 主資料載入時，IV 是從 App 內部儲存空間的 `encryption/aes_iv` 檔案讀出來的（APK 裡沒有這個檔案，沒有 root 讀不到）。
- 突破點：拿 3,000 個劇情檔的第一個區塊做 AES-ECB 解密，前 2 bytes 全部是 `0D CE` → 所有檔案共用同一個 IV，而且明文開頭固定（推測是 zlib 的 `78 9C`）→ IV 開頭應該是 `0D^78, CE^9C` = `"uR"`。
- 網路 API 那段程式（`0xbcfae8`）用同樣的混淆方式組出一個 16 bytes 的值：
  ```
  S = @0x1bae580（16 bytes）, T = @0x1bafc26
  iv[i] = T[S[i] ^ 0x4E] ^ 0xCF
  ```
  結果開頭正好是 `uR` → 這就是 IV。

### 檔案格式

```
.enc = AES-256-CBC(key, iv, PKCS#7) → zlib → FlatBuffers
```

FlatBuffers 裡的字串（`flatbuffers::String`）內容再用 **XXTEA** 加密（標準 XXTEA，最後一個 word 存明文長度；解密程式在 `0x14d1584`、字串解密在 `0x83a5a4`）。

### XXTEA 金鑰

- 程式預設金鑰是明文 `"xjhdgUCPiqyxdq8d"`（`0x1acf230`），**但沒有用到**。
- MasterData 初始化時（`0xc20de4`）會用混淆的值覆寫金鑰緩衝區 `0x2398ef9`：
  ```
  S = @0x1bbab50（16 bytes）, T = @0x1bbb86c
  key[i] = T[S[i] ^ 0x44] ^ 0xF6
  ```
- 實際用的金鑰：16 bytes ASCII，金鑰是 4 個 little-endian uint32。

金鑰不寫在程式裡：`tools/keys.py` 會從使用者自己的 `libapp.so` 用上面的公式算出來，存成 `keys.json`（不發布），`tools/dmcrypto.py` 讀取它。

## 4. 劇情指令格式（novelCommand）

用 `tools/fbdump.py`（不需要 schema 的 FlatBuffers 啟發式解析器）觀察：root table 欄位 0 是指令陣列，每個指令是：

| 欄位 | 內容 |
|---|---|
| 0 | 指令 ID |
| 1 | 所屬 novel ID（對應 `novel` 表欄位 0） |
| 2 | 指令類型（**XXTEA 加密的 int32**，解開後是 1–74 的列舉值，見第 8 節） |
| 3–9 | 字串參數 |

### FlatBuffers 解析的陷阱（都已在 `tools/fbdump.py` 處理）

1. **對齊是從緩衝區尾端算起**：FlatBuffers builder 由後往前建，int64 欄位滿足 `(len(buf) - pos) % 8 == 0`，不是 `pos % 8`。
2. **同一欄要整欄判斷型別**：單看一筆資料無法分辨 int64 和「int32 + padding」。改成同一個陣列的所有資料列都 8-byte 對齊、而且後面都有 ≥ 8 bytes 空間，才當 int64。資料列很少的小檔案仍可能誤判，用到 ID 時要再用低 32 位元比對一次。
3. **數值欄位都是加密區塊**：程式的 `flatbuffers::Xxtea::DecryptScalar`。解開後最後一個 word 是資料長度：
   - 8 bytes = (int32, 4) 或 (byte, 1)
   - **12 bytes = (int64 低位, 高位, 8)**：最初只處理 8 bytes，int64 欄位被讀成密文，看起來像雜湊。實際上 episode／stage／novel 等 ID（例如 episode `7090120210`）、所有日期（94 個欄位，例如 adventureEpisode f6/f7 開催期間）都是 int64。2026-10 全面稽核 431 張主資料表與 11,462 個劇情檔，只存在 8／12 bytes 兩種；改成「先試長度特徵」後也修好了約 150 個被誤判成字串／子表的數值（其中一個讓グランド・デイ（復刻）少了一個 stage），以及 voice／lotteryCharacter／enemy 三張整張解壞的表。
4. **陣列和子表格的判斷**：先試陣列（每個元素都是合法字串或表格），失敗才當子表格；否則只有 1 個元素的陣列會被誤判成表格。

範例（novelCommand751000001）：
```
背景   single_image.65980080 / background / fade / 1.0
BGM    bgm.dungeon_normal / 0.0
立繪   novel_portrait.bel_normal / normal / center
對話   novel_portrait.bel_normal / normal / middle / voice.main00_step1_bel_001 / ベル / ５階層まで来ちゃったけど、大丈夫かな……
```

## 5. 批次解密

`tools/decrypt_all.py`：用多個行程把以下檔案全部轉成 JSON，存到 `dec/`（11,893 個，0 錯誤，約 2 分鐘）。
- `x/pack/assets/master/divide_novel_command_enc/*.enc` → `dec/novel/`
- `x/base/assets/common/master/divide_enc/*.enc` → `dec/master/`（431 個主資料表）

### 劇情相關的主資料表

| 表 | 筆數 | 內容 |
|---|---|---|
| `adventure` | 568 | 冒險分類，例如「メイン 第1部 ベル編」 |
| `adventureEpisode` | 1,261 | 話，例如「冒険者　前編」 |
| `adventureStage` | 22,153 | 關卡，連到 `novel.xxx` |
| `novel` | 11,489 | 劇情 key 和標題；劇情指令的欄位 1 = novel ID |
| `novelPortrait` | 1,666 | `novel_portrait.bel_normal` → 檔名 `bel_normal` |
| `singleImage` | 33,170 | 背景、CG |
| `bgm` | 217 | `bgm.main_theme` → `bgm_main_theme` |
| `scenarioLwf` / `movieUsm` / `movieLwf` | | 特效動畫、影片 |
| `phase` / `phaseItem` | | 分段下載的內容（BGM 等） |

ID 欄位（int64/int32）看起來是字串 key 的雜湊值。

## 6. 素材來源

### APK 內

- 立繪：`x/pack/assets/files/character/novel_portrait/`（17,420 個檔案，256 MB）
- 只有 1 首 BGM（main_theme）、UI 音效

### 手機內部空間（讀不到）

`dumpsys diskstats`：App 資料 4.07 GB，在 `/data/data/com.danmemo`，沒有 root 讀不到。

### 原本的 CDN 還活著

`libapp.so` 裡有 `https://cdn-danmemo.akamaized.net`，還有 cocos2d-x AssetsManager 的設定：
```
remoteManifestUrl: {}/manifests/jp/png/project.manifest.1/0880e4f102c7a71c775762db73e12acf
```

可下載的清單（存在 `cdn/`）：

| 清單 URL（`manifests/jp/png/<名稱>/0880e4f102c7a71c775762db73e12acf`） | 內容 |
|---|---|
| `project.manifest.1` | 基本（主資料、UI、字型）170 MB |
| `project.manifest.2` | 立繪、轉蛋圖、片尾影片 0.54 GB |
| `project.manifest.3` | **語音 2.27 GB、背景 378 MB、BGM 147 首、scenarioLwf 571 個、音效 852 個、過場影片** |
| `project.manifest.4`–`8` | 空的 |
| `single_image.manifest` | 背景、CG 21,749 張 1.06 GB |
| `voice_episode.manifest` | 活動語音 zip 401 個 6.81 GB |
| `area_atlas.manifest` | 場景地圖 2.83 GB（劇情用不到） |
| `phase.manifest.1`–`8` | 空的 |

（`project.manifest.2`、`.3` 不在 `.1` 的清單裡，是試編號發現的。）

素材網址：`https://cdn-danmemo.akamaized.net/<path>`，`path` 格式是 `contents/<相對路徑>/<md5>.<副檔名>`。

另一個網址 `storage.googleapis.com/argo-ap4zsi86n4q` 抽樣看只有オフライン版的說明頁面，沒有素材。

### 素材格式（抽樣確認）

| 類型 | 格式 | 網頁可否直接用 |
|---|---|---|
| BGM、語音、音效 | Ogg Vorbis | 可以 |
| 背景、CG | JPEG 1280×720 | 可以 |
| 立繪 | PNG（cocos plist 圖集） | 要解析 plist |
| 劇情特效 | GREE LWF 二進位（`LWF\0`） | 用 lwf.js |
| 影片 | CRI USM（`CRID`） | 要轉 MP4 |

## 7. 繁中版調查（結論：目前拿不到劇情）

- 繁中版 `com.tw.danmemo`，2024/2/29 停服。使用者提供第三方下載的 `com.tw.danmemo_15.1.0.xapk`，**只解壓做靜態分析，沒有安裝**（`tw/`）。
- 繁中版 `libapp.so` 裡的 CDN 是 `https://cdn-danmemo.akamaized.net/tw`，API `https://api-danmemo-tw.wrightflyer.net`（已停）。
- 金鑰和日文版相同（APK 內建主資料可以用 `tools/dmcrypto.py` 解開），但內建的主資料表都是空的，真正資料當初都從伺服器下載。
- APK 內建清單的版本雜湊值是 `ff56abce6a2a2be426f9f2da25503da7`：
  - `manifests/tw/png/project.manifest.{1..4}/<ver>`（加不加 `/tw` 前綴都試過）→ 全部 **403**
  - 但內建清單裡的實際素材路徑 `https://cdn-danmemo.akamaized.net/contents/<path>/<md5>.<ext>` → **200**
  - → 繁中版素材和日文版共用一個以 MD5 定址的 `contents/` 區，**檔案還在**，但沒有清單就不知道劇情檔的 MD5。
- Wayback Machine 查 `cdn-danmemo.akamaized.net`、`api-danmemo-tw.wrightflyer.net` 的清單網址：沒有存檔。
- 網路上也沒找到社群備份的繁中劇情。
- **舊手機實測（Motorola razr 2020，Android 12，繁中版 14.1.3，未 root）**：
  - 套件旗標沒有 `ALLOW_BACKUP`（且 targetSdk 31 在 Android 12 也不支援 adb backup）。
  - 外部儲存 `/sdcard/Android/data/com.tw.danmemo/` 只有廣告 SDK 快取（supersonicads、UnityAdsCache，104 檔、197 MB），**沒有遊戲資料**；遊戲清單與劇情在內部空間（`getFilesDir()`），沒有 root 無法以正規方式讀取，不嘗試繞過系統保護。
  - 14.1.3 APK 內建清單版本 `f470191d20860e52c44b0e4c448ce5dc` → CDN 一樣 403。
  - 2026-10-12 再查：一般權限可讀的地方（`Android/data|obb|media`、整個共用儲存區）都沒有遊戲資料；`run-as` 不可用（非 debuggable）。開啟遊戲錄 logcat：只到 WFS 標誌 → 帳號錯誤（伺服器已關），記錄裡沒有任何網址、清單版本或 md5（只有 cocos 貼圖快取的本機路徑）。另外，APK 內附清單中只有繁中才有的檔案抽樣 17/18 仍可從 CDN 下載：**繁中檔案還在，缺的只是清單**。
- **要繼續的唯一條件：**找到繁中版最終版本的 `project.manifest`（或它的版本雜湊值）。如果有人還留著當年裝有繁中版的 root 手機資料、或封包紀錄，就有機會。

## 8. 指令對照（novelCommand 欄位 2）

類別名稱來自 `libapp.so` 裡的 `NovelCommand*` 類別，配合參數和前後指令的統計推斷。參數用 `/` 分隔（欄位 3–9）。

| # | 推定類別 | 參數 | 播放器實作 |
|---|---|---|---|
| 1 | ImageShow | 圖, 圖層(background/foreground/middle), 轉場, 秒 | ✔ 同圖層交叉淡入 |
| 2 | ImageHide | 圖, 圖層, 轉場, 秒 | ✔ 淡出圖片（常見用法：前景黑圖蓋住畫面 → 擺好角色 → 用 2 淡出黑圖）※最初誤判為顯示，造成整段黑畫面 |
| 3 | ImageShow（前景） | 同 1 | ✔ |
| 4 | EffectShow | lwf, x, y, wait/no_wait, fade, 淡入秒, 旋轉 | ✔ 場景特效；持續到 53、淡出（19）或播完變空白（dagger/graywind 等一次性特效）。重發同名特效會取代已播完停住的舊實體 |
| 5 | CharacterSet | 立繪, 表情, 位置(left_end/left/center/right/right_end) | ✔ 先放好但不顯示；**重設縮放**（2,391 次是在特寫放大中直接重設，原作顯示正常大小） |
| 6 / 7 | CharacterShow / Hide | 立繪…(最多 3 個), 轉場(fade/slide/immediately), 秒 | ✔ |
| 8 | CharacterAction | 立繪, dx, dy, ?, 情緒符號, over | ✘（情緒氣泡素材未對應） |
| 9 | CharacterAction（hop） | 立繪, , hop | ✔ 跳動 |
| 10 | CharacterFocus | 立繪, on/off/auto | ✔ 非說話者變暗 |
| 11 | TalkShowWait | 立繪, 表情, ?, 視窗位置, 語音, 名字, 文字 | ✔ 等點擊 |
| 12 | TalkShow | 同 11 | ✔ 不等點擊（自動播放段落） |
| 14 | TalkSelectionShow | A 文字, 秒, B 文字, 秒, 語音(空白分隔), 名字, A/B 合併文字 | ✔ 選項 |
| 15 | TimeDelay | 秒 | ✔ |
| 16 | QuakeStart | 對象(all/background/character/立繪), ?, 幅度, ?, 秒 | ✔ |
| 17 | MovieStartWait | movie_usm, skip_enable… | △ 需先把 USM 轉成 MP4 |
| 18 | SeStart | se, 延遲 | ✔ |
| 19 / 20 | ScreenChangeFadeOut / FadeIn | 秒 | ✔ 淡出後**整個場景重置**：清掉場景特效、角色、中景／前景圖、旁白（保留背景）。4,516 個特效從未被關閉、而後都接著淡出；23k 次角色在淡出後不再出現或被重新設定 |
| 21 | TitleShow | 標題, 副標題 | ✔ 標題卡 |
| 22 / 31 | BgmStart / BgmChangeDefault | bgm, 淡入秒 | ✔ |
| 23 / 24 / 25 | ImageMove / Scale / Rotate | 圖, x, y / 倍率 / … , 秒 | ✔ 不阻塞（和後續指令同時進行的鏡頭移動） |
| 27 | CharacterMove | 立繪, x, y, 秒, relative/absolute | ✔ |
| 29 | TalkClose | 秒 | ✔ 同時淡出旁白文字 |
| 30 | BgmStop | 淡出秒 | ✔ |
| 32 / 52 | ScreenFlush | 色, 圖層, 入, 停, 出 | ✔ 閃光 |
| 33 / 42 | SeLoopStart / SeLoopStop | se, 音量, 淡入 | ✔ |
| 36 | CharacterAppear | 立繪, 表情, x 或 (起點 x, 終點 x, 秒) | ✔ 可滑入 |
| 37 | VolumeSet | bgm, 音量, 秒 | ✔ |
| 38 | （受傷震動） | 立繪, 強度 | △ 用震動代替 |
| 39 | CharacterFace | 立繪, 表情 | ✔ |
| 40 | ImageSet | 圖 | ✔ 預載並重設位置 |
| 67 | ImageRemove | 圖 | ✔ 立即移除（常接在 2 之後） |
| 41 | CharacterScale | 立繪, 倍率, 秒 | ✔ |
| 44 | DescriptiveShow | 色, 透明度, 秒 | ✔ 旁白遮罩 |
| 45 | DescriptiveText | 色, 轉場, 位置, 秒, 語音, 字級, 文字 | ✔ 旁白 |
| 50 | ScreenChangeFadeTo | 色, 圖層, 透明度, 秒, wait | ✔ |
| 53 | **EffectHide** | lwf, , fade/immediately, 秒, wait | ✔ 關閉 4 開的特效（1,413/1,434 次緊接在同名 4 之後）。最初誤判為顯示，集中線等特效一直留在畫面上 |
| 54 / 55 / 56 | LwfSet / LwfShow / LwfHide | lwf, 實例名, x, y / LWF, 秒, wait | ✔ |
| 58 | LwfHide（依實例名） | lwf, 實例名, 秒 | ✔ |
| 59 / 68 | LwfRotate / LwfMove | … | ✔ |
| 57 / 69 / 70 | LwfFlip / LwfZOrder / LwfParent | | ✘ |
| 60–63 | AnimationText Set/Show/Move/Remove | id, 座標, 色, 字級, 文字 | ✔ 字幕、片尾名單捲動 |
| 64 / 65 / 66 | PostEffectGroupSet / Start / End | 圖層(background/middle/background_middle/…_effect/all) / 類型 | ✔ blur、color_multiplier、custom_color_correction（SVG 矩陣）、sepia、grayscale；✘ gradient_multiplier（210 次）、rim_light（161 次） |
| 71 / 74 | BattleSimulate / CompleteMission | | 忽略 |

文字標記只有振假名一種：`[r=よみ]漢字[/r]`。

## 9. 網頁播放器

```
tools/build_web.py   dec/ + 素材 → web/data/（目錄、每段劇情 JSON、鑑賞資料）
tools/serve.py       本機伺服器（支援 Range），http://localhost:8080/
web/index.html       首頁 / ストーリー / その他 / キャラクター / カード
web/js/player.js     播放引擎（1280×720 舞台，DOM + Web Animations + LWF canvas）
web/js/app.js        路由、目錄、播放頁（AUTO / SKIP / LOG / 音量 / 已讀紀錄）
web/js/gallery.js    立繪鑑賞（表情切換）、卡片鑑賞
web/vendor/lwf.js    GREE LWF JavaScript 執行環境（Zlib 授權，附 LWF-LICENSE.txt）
```

- 素材路徑由 `build_web.py` 預先解析，寫進每段劇情 JSON 的 `res`，播放器不用查表。網頁路徑 `r/<i>/` → `config.json` 的第 i 個 `asset_roots`（符號連結）。
- 時序：原作引擎**每條指令至少佔一格畫面（1/30 秒）**；連發 30 把匕首（每輪 5 條指令）原作約 6 秒。播放器在非快轉時對每條指令補足一格。
- 以原作錄影逐格比對修正過的規則：見第 8 節的 4／5／19／53／65。
- 劇情目錄：分類（adventure 欄位 2）→ 冒險 → 話（adventureEpisode）→ 關卡（adventureStage，開頭劇情在欄位 28）→ 關卡內事件（adventureEncounter 欄位 8／9，依欄位 2 排序）。目錄收錄 5,521 段，其餘 5,941 段依 key 前綴放在「その他」。
- 立繪：`body.png` + 表情圖貼在 `cutout.plist` 的座標（左上角為原點）；沒有 body 的資料夾，每個表情都是完整圖。
- LWF：**所有特效都以原點為中心製作**（讀 LWF 資料的 translates/matrices，座標都分布在原點兩側，和畫布尺寸 10×10、200×200、640×360、1280×720 無關）。一律把原點放在指令的 (x, y)、不縮放；y 軸從 cocos 朝上換算成網頁朝下。※過程中試過「依畫布尺寸判斷左上角原點並放大」，造成睜眼遮罩錯位、流星變白霧、回憶煙霧只剩四分之一，最後用資料確認後統一成這個規則。
- 驗證：`tools/smoke.py` 用無頭 Chromium 以快轉模式隨機播放 200 段，0 逾時；抓到並修掉兩個錯誤（方法和屬性撞名、快轉時的暫時死區）。

### 缺少的素材

紀念版清單只收紀念版會播的篇目，但劇情資料收了全部 11,462 篇。用國際版清單補下載（內容相同的檔案網址相同）後，剩下兩邊都沒有的：語音 819、劇情插圖 156、音效 26、影片 1 處引用（2024-02 國際版停服之後的日版內容）。播放器遇到時直接略過。

## 10. 英文版資料（使用者提供的 Google Drive 備份）

- 來源：Reddit 分享的 Google Drive 資料夾，是 global 版 `com.eu.danmemo` 的 App 資料備份（附 2023-12-22 的 APK）。
- 用 Drive 的 `embeddedfolderview?id=` 頁面列出檔案（`tools/gdrive_ls.py`），用 `uc?export=download&id=` 下載（`tools/gdrive_get.py`）。gdown 因為大型資料夾而卡住，改用這個方法。
- `contents/1/master/divide_novel_command_enc/` 有 **5,500 個英文劇情檔**，`contents/1/master/divide_enc/` 有 431 個主資料表，還有英文版的 manifest。
- **和日文版用同一組金鑰**，解開後就是官方英文翻譯：`Bell: I came all the way down to Floor 5. I hope I'll be okay...`
- 用途：第二階段翻譯的對照或底稿；英文版的素材資料夾也補上了紀念版缺的素材（約 10,577 個檔）。
- **可以單獨當資料來源**（2026-10 驗證）：dump 結構是 `contents/1..8/files/…`、`contents/1/master/divide_enc|divide_novel_command_enc`、`voice_root`（活動語音已解壓）、`single_image_root`，直接列進 `config.json` 就能建置（5,500 篇、目錄 5,261 篇、784 張卡）。國際版 APK 只有 32 位元 `libapp.so` 且表格不同，`keys.py` 不支援；金鑰相同，改用日版紀念版的 `libapp.so`。缺口：插圖 2,175 處不在國際版、沒有相簿。英文使用者流程寫在 `README_EN.md`。
- 另一份 dump（`contents.part1-6.rar` + 同一份 APK 與 `Directory.txt`）是同一批資料的壓縮版。
- 相簿：國際版資料沒有 f29/f30，`build_web.py` 內建紀念版的 48 篇清單（`ALBUM_DEFAULT`）套用到國際版的標題、橫幅、劇情；dump 缺最後 9 篇活動的劇情檔，所以是 39 篇。純英文環境（沒有任何日版檔案）實測：解密 0 錯誤、建置正常、抽播 40 篇 0 逾時。

## 11. 發布設計（程式與資源分離）

- 發布範圍只有 `tools/`、`web/js`、`web/css`、`web/index.html`、`web/vendor/`、`docs/`。
- `.gitignore` 排除所有遊戲資源和衍生資料：`apk/ x/ tw/ en/ cdn/ assets/ dec/ wayback/ keys.json web/data/ web/r/`。
- 說明文件：`README.md`（中文）、`README_EN.md`、`README_JP.md`。程式裡沒有寫死的個人路徑或區網 IP（測試工具用 `DANMEMO_URL`）。
- 程式裡沒有金鑰；使用者用自己的 `libapp.so` 執行 `tools/keys.py` 產生。
- 使用者自備資源的流程（之後再整理成 README）：
  1. 從自己的手機用 adb 取出 APK → 解壓
  2. `tools/keys.py` 產生金鑰
  3. 素材：用 `tools/download.py` 從 CDN 下載，或指定自己的 App 資料備份資料夾（像英文版備份那種 `contents/1..8` 結構）
  4. `tools/decrypt_all.py` → `tools/build_web.py` → `tools/serve.py`

## 12. 卡片資料（pc 表）

| pc 欄位 | 內容 |
|---|---|
| 1 / 2 / 3 | 稱號 / 角色名 / 「★４：指揮官」標籤 |
| 4 | 排序用（**不是**稀有度，最初誤用，出現 504 顆星） |
| 7 | character key |
| 9 | 類型：1 冒險者、4 アシスト（1012 開頭的 ID 大多是アシスト；含「テスト用」測試卡，排除） |
| 10 | characterSpine |
| 12 | 類型：1 物理攻撃型、2 魔法攻撃型、3 回復型、4 バランス型、5 防御型（名稱來自 message 表） |
| 13 | 所屬（pcAffiliation） |
| 14–19 | 各ランクの pcJob（★4 卡只有 ★4〜★6 三個） |
| 20 | 限界突破用 pcJob |
| 22 / 24–26 / 27 / 28 | pcSkill：通常攻撃 / スキル1–3 / カウンター / 必殺技 |
| 29,30 … 37,38 | （解鎖順序, pcAbility）× 5：アビリティ |
| 46 | 稀有度 |
| 47 | 經驗值曲線（pcLevelStep 群組；欄位 3 = 累計經驗值） |
| 48 / 54 | HP 基礎值 / MP 基礎值 |
| 49 / 50 / 51 / 52 / 53 | 基礎值：力 / 魔力 / 敏捷 / 耐久 / 器用（56 不是能力值） |
| 90 | 英雄昇華群組（heroSublimateLevelStep 欄位 1），沒有就不能昇華 |
| 76 | characterCostume（服裝） |
| 78 | 期間限定（加密布林值；解開是 值 1／長度 1） |
| 92 | 屬性位元：1 火、2 地、4 風、8 水、16 雷、32 光、64 闇（和技能推斷 480/487 一致，以此為準） |
| 96 | 英雄祭（13 張，正好是有動態卡面 lotteryLwf 的卡） |
| 79 | attackPattern |

### 能力值公式（用紀念 App「キャラ詳細」畫面驗證）

透過 adb 擷取手機畫面（`adb exec-out screencap -p`）並用 `adb shell input tap` 切換限界突破、英雄昇華，對 3 張卡（★1 冒険者 ベル、★4 英雄願望 ベル、★4 新春白兎 ベル）共 14 種狀態逐格比對，**全部完全吻合**。App 顯示的是最大ランク、熟練度最大的狀態。

```
熟練度(等級)  L = 60 + 4 × 限界突破
pre[s]   = 基礎值[s] + Σ(各ランク盤 s 的面板) + Σ(限界突破面板 1..5×突破數 的 s)
(+N)[s]  = floor(pre[s] × アビリティ%[s] / 10000) + 英雄昇華累計[s]
能力值[s] = pre[s] + (+N)[s]                         s ∈ 力 耐久 器用 敏捷 魔力
HP = pc[48] + Σ_{l=1..L} pcLevelStep(群組 pc[47], l)[4]  + 英雄昇華累計 HP
MP = pc[54] + Σ_{l=1..L} pcLevelStep(群組 pc[47], l)[10] + 英雄昇華累計 MP
物攻 = 力、魔攻 = 魔力、防御 = 耐久
```

- アビリティ%：卡片欄位 30/32/34/36/38 指向的 pcAbility 中，欄位 5 = 16 的是百分比加成，欄位 6 = 萬分比，欄位 7 = 能力位元遮罩。同一能力的百分比先加總再乘（分開取整會差 1）。
- 英雄昇華：heroSublimateLevelStep 欄位 7 = 階段 1–6，欄位 8–14 = HP、MP、力、魔力、敏捷、耐久、器用 的固定加成，累加到選擇的階段。
- 等級表 pcLevelStep：欄位 3 = 累計經驗值、欄位 4 = 該級 HP 增量、欄位 10 = 該級 MP 增量。
- **能力評價字母**：判斷函式在 libapp.so `0xd9798c`（依能力位元取值後查表），門檻表由靜態初始化 `0x7206c0` 從 `0x1bf40f0` 起的唯讀資料建立。每項能力 12 組 (字母編號, 門檻)，取第一個「門檻 ≤ 數值」的字母；編號 1–12 = SSS, SS, S, A, B, C, D, E, F, G, H, I，圖檔 `files/icon/character_detial/evaluation_{編號}.png`。
  - 一般卡：力 2000/1000/700/400/350/300/250/200/150/100/50；魔力 1800/900/610/320/280/240/200/160/120/80/40；敏捷 1400/700/470/230/200/170/140/110/80/50/20；耐久 1500/750/500/230/…（低階同敏捷）；器用 1460/730/490/230/…。
  - **アシスト卡**（pc[9] == 4）用另一張表、沒有 SSS：力/魔力/敏捷/器用 SS500 S400 A280 B245 C210 D175 E140 F105 G70 H35；耐久 SS500 S350 A200 B175 C150 D125 E100 F75 G50 H25。（最初誤以為是バランス型用的，用 App 的バランス型卡驗證後更正。）
  - 用 App 畫面約 60 個（數值, 字母）驗證，全部吻合（含 SSS：［光炎憧憬］力 2086）。
- **屬性圖示**：`element_{pc[92]}.png`；技能圖示用 `element_{pcSkill[14]}.png`（加 128 的是帶武器的金框版）。技能的消費 MP = pcSkill[5]。
- **技能頁（照 App）**：冒險者 = 必殺技(28) + 技(24–26) + スキル/発展アビリティ；不顯示通常攻擊、カウンター。アシスト = 只有アシストスキル：突破 0–4 顯示 pc[25]（＋），突破 5 顯示 pc[26]（＋＋）。アシスト沒有屬性、類型。
- **動態卡面（英雄祭）**：`files/lwf/lotteryLwf/lwf_lottery_ef_<id>/lwf_ui_ef_<id>_{status_l,rectangle,lottery}.lwf`，只用自己的特效貼圖，是疊在靜態卡圖（status_l / all_rectangle / lottery.png）上的光線與煙霧，原點 = 卡圖中心、1:1。
- **抽卡演出**：オフライン版沒有收錄，從英文版 Google Drive 備份的清單找到 CDN 上的實際檔案補齊（素材共用、以 MD5 定址，`contents/...` JP/EN 相同）：
  - 開場影片 `files/movie/{argo,another}_gacha_op_0{2,3,4}.usm`（依稀有度）。USM 音訊有 ADX（檔頭 0x8000）和 HCA 兩種，`tools/usm.py` 依檔頭自動判斷。
  - 演出動畫是遊戲自己的一套 LWF：`files/lwf/uiLwf/lottery/argo_gacha_cut_0{3,4,6,7}_*`，角色圖、名牌、台詞是可替換貼圖（`lwf_replace_*`，用 lwf.js 的 imageMap 替換；data: URL 會被加前綴而失效，替換圖要用 `/` 開頭的絕對路徑或 `/transparent.png` 遮掉）。本專案用 cut_07（登場）＋替換卡圖 `lottery.png`、剪影 `white.png`，名牌貼圖遮成透明、改用畫面疊的日文版。 lwf.js 的 Canvas 渲染會參考 canvas 的顯示尺寸，所以**不能用 CSS transform 縮放 canvas**（會被二次放大、只剩中間）；改成把 backing 設成實際裝置像素（CSS 尺寸 × devicePixelRatio）、用 `property.scaleTo` 讓 LWF 自己縮放，高 DPI 螢幕才正確。
  - 每張卡的抽卡圖 `lottery.png`、剪影 `white.png`、語音 `pc[75]` 都下載回來（772／759／649 張）。**語音確認是日文**：和日文版同名檔逐位元相同（比對 401 個 MD5 全同）。
  - **限制**：cut 動畫的稀有度橫幅（ULTIMATE 等）烤在 EN 貼圖裡，是英文；台詞字幕 JP 版在任何已有資料都沒有（voice.enc 無台詞文字、繁中清單拿不到、EN 的是英文圖），故不顯示字幕。

- **ステイタス盤**：pcJob 欄位 11 = pcAbilityPanel 群組（欄位 1），每個面板的欄位 3 指向 pcAbility。pcAbility 欄位 1 = 50 是能力值面板，欄位 6 = 加成值，欄位 7 = 位元遮罩（2 力、4 魔力、8 敏捷、16 耐久、32 器用）。面板只加這五項。
- **限界突破**：限界突破 pcJob 的面板 25 個，每 5 個是一段（+1〜+5）。
- **服裝劇情**：adventure 分類 4（衣装）每個角色一話，各關卡的欄位 15 = 卡片 ID，劇情在欄位 28（+ encounter）。790 張卡中 319 張有服裝劇情。
- 網頁：`data/gacha.json` = `{stats:[…], cards:[…]}`；卡片面板顯示稱號、稀有度、類型、所屬、各ランク盤與限界突破的上昇值（可選 +0〜+5）、技能、アビリティ、服裝、服裝劇情（`#/play/<novel>?card=<id>`，返回卡片）。

## 13. 紀念版相簿（アルバム）

- 遊戲內「アルバム」→「周年ストーリー／イベントストーリー」，官方挑選 48 篇（周年 15、活動 33）。
- 資料：adventureEpisode **f29 = 分頁**（1 周年、2 活動），**f30 = 排序（由大到小）**，f6/f7 = 開催期間，f24 = 約三個月後的另一個期限。橫幅 = `files/adventure/episode_list_cell/<episode ID>.png`（605×140，紀念版只收這 48 張）。
- 開催期間的字樣來自 message `home_quest_event_open_period`；結束日 ≥ 2030（常駐）不顯示。f30=49「それは遥か彼方の静穏の夢」（アルフィアIF）遊戲沒顯示，網頁版收錄。
- 點進去是有劇情的 stage 清單；每個 stage 依 NORMAL／HARD／VERY HARD 各有一份，劇情相同（或為子集），只列一次。
- ストーリー 頁：相簿已收錄的篇目改成連結；同內容復刻（含台詞相同的 `_ex` 劇情檔：416 完全相同、16 只差演出）合併；台詞不同的 6 篇保留。

## 14. 素材來源與 CDN

- CDN 兩層：清單 `manifests/<地區>/<格式>/project.manifest.N/<版本號>`；檔案 `contents/<遊戲內路徑>/<檔案內容 md5>.<副檔名>`。**檔案以內容定址**，日版與國際版共用同一個 `contents/`，同內容同網址；沒有 md5 一律 403、不能列目錄。
- 日版紀念版清單（`0880e4f1…`）還在；日版線上版清單（`a3876e8d…`，見 15.1.0 apk 的 bundled manifest）png/dds/pkm 全部 403。15.7.x xapk 是紀念版。
- `fill_gaps.py` 最初以國際版清單為準，結果把 47 張相簿橫幅和 80 個檔（劇情 LWF 75、6 周年影片 4、插圖 1）換成了英文版；改成日版清單優先、國際版補缺，並移除蓋掉 APK 版本的副本。
- 非相簿活動的列表橫幅只有國際版有：28 張是日文原圖（`build_web.py` 的 `JP_TEXT_CELLS`），60 張是英文。日本攻略站（ゲーマンブ）有部分日文版的縮小圖（400×92）。
- 抽卡台詞文字不在任何資料裡；`voice` 表確認 874 句抽卡語音中 827 句是專用錄音、47 句沿用劇情語音。

## 15. Wayback Machine（擱置中，資料已下載）

- `cdn-danmemo.akamaized.net/*` 收錄約 32k 個網址：**沒有清單**；`contents/files/` 的 5,216 個素材都不含劇情缺的部分。
- **8,150 張日版公告圖**（`webview/production/notice/img/<md5>`，2019–2024，最大 2666×1500）CDN 仍在供應，已全部下載到 `wayback/img/`（md5 驗證）。
- 日版公告頁（約 4,800 頁，`api-danmemo.wrightflyer.net/asset/notice/…`、`news-danmemo.wfs.games/external/notice/…`）下載中，用來把公告圖對應到活動。`tools/wayback_get.py`。

## 16. 舊制 CDN 與舊版 APK 清單（日文原版素材）

- 2019 年以前的客戶端用**舊制網址**：`<CDN>/<40 位雜湊>/contents/<路徑>`，不需要 md5。雜湊是**每個檔案各自的**（該檔最後修改時的版本），所以單一前綴只對應一份快照。Wayback 只存到一個（`cc73f149…`，約 2017-07-13），裡面有開服初期 108 張日文名牌。
- 舊制 APK 內附清單的 `remoteManifestUrl` 是 `<CDN>/<40 位>/png/production/project.manifest.N`，**到現在仍可下載**。8.2.0（約 2019 年 9 月）的清單有 44,637 筆，每筆帶自己的舊制網址與 md5（抽驗全數相符）。10.4.3、10.9.1、13.x 以後已是新制，清單都已刪除（403）。APKPure 只留到 13.0.1，8.x/10.x 是從 apkhere 找到的。
- `tools/legacy_manifests.py <apk…>` 讀出網址並存到 `cdn/legacy/<版本>/`；`fill_gaps.py` 的優先順序是紀念版 → 舊版線上清單（新版優先）→ 國際版。劇情背景（single_image）兩邊只是 JPEG 重新壓縮，已有的就不重抓；橫幅、關卡列表圖、劇情 LWF 標題圖是實際的英日文字差異，會換成日版。
- 結果：日文名牌 342/790 張（存到 `files/lottery/name_jp/`，和國際版英文名牌分開），劇情頁日文橫幅 28 → 160 篇（`build_web.py` 用 md5 對日版清單判斷是否為日文原版）。
- **抽卡台詞是圖片**：`files/lottery/text/<卡片ID>.png`（1024×1024 直書白字），由文字 cut `argo_gacha_cut_04_moji_3` 的 `lwf_replace_txt_cut04.png` 顯示；背景槽（`lwf_replace_bg_cut04.png`）在 8.2.0 客戶端維持 cut 自帶的黑底（`character_flash` 全是空白佔位圖，`lottery/background/<卡池ID>` 是卡池列表畫面用的）。紀念版清單 0 張；8.2.0 清單 301 張（對得上 281 張卡），國際版 713 張。之前「台詞文字不存在」的結論是只找文字資料造成的誤判。演出順序改為：波形閃光 → 台詞（有圖才播，語音從這裡開始）→ 角色登場。日版存 `files/lottery/text_jp/`。
- 再找更晚的舊制版本（8.x 最後一版或 9.x）可以把涵蓋範圍延伸到 2019 年 9 月以後。

## 進行中

- [x] 下載素材、指令對照、網頁播放器（劇情、立繪鑑賞、卡片鑑賞）、USM → MP4
- [x] 英文版劇情與主資料；國際版 dump 單獨建置驗證（README_EN）
- [x] 卡片：能力值公式、評價字母、屬性、限定／英雄祭、アシスト、技能、動態卡面、衣裝劇情
- [x] 資料來源設定檔（config.json），程式不含金鑰與素材
- [x] 數值解碼修正（int64）、紀念版相簿、ストーリー 去重與相簿連結、キャラ別
- [x] 播放器：EffectHide、淡出重置場景、CharacterSet 重設縮放、sepia／grayscale、每指令一格、非表示、設定面板、LOG 切換
- [ ] gradient_multiplier、rim_light 濾鏡
- [x] 介面多語系：`web/js/i18n.js`（日文原字串為鍵，英文／中文翻譯；分類、能力值、屬性名也經過它；開催期間依語言格式化），右上角切換，存在 localStorage
- [x] `fill_gaps.py` 檢查所有已設定的素材目錄、讀取備份內附的清單；`DANMEMO_CONFIG` 切換設定檔
- [x] 舊版 APK 清單：8.2.0 → 日文名牌 342、日文橫幅 160（第 16 節）
- [ ] 找 8.2.0 之後、轉新制之前的最後一版 APK
- [ ] Wayback 公告圖的用途（活動封面？）
- [ ] 建立日英對照（第二階段翻譯用）
