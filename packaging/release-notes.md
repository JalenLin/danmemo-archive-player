**v1.1.0 — the Android app**

New: **DanMemoPlayer-android.apk**, the same player built and played on the phone, no computer needed (Android 7.0 or later, 64-bit). The app includes a small LGPL ffmpeg, so the cutscene movies are converted on the phone too.

1. Put your extracted app-data backup on the phone. Extracting the RAR parts on the phone took about 2 h 10 min on a Pixel 10 Pro: Android handles each of the ~260,000 files one by one. To speed it up, set the extractor app's battery usage to Unrestricted, keep the screen on with it in front, pause Play Store auto-updates, and put an empty `.nomedia` file in the target folder so the gallery stays clean. Copying an extracted `contents` folder from a computer over USB works too.
2. Install and open the app, allow "manage all files" (only used to read the backup), choose the global APK (or the JP memorial app's `.xapk`) and the backup folder, and tap Build. It takes about 15–25 minutes (Pixel 10 Pro ~16, Pixel 5 ~24), plus the optional download (~1.6 GB). The build keeps going with the screen off, only slower.
3. Open the player. "Keep screen on" (while playing / always / off) is in the player's settings.

Windows: the setup page now has the player's language menu, and the player's toolbar fits narrow windows. **Updating from v1.0.x:** replace `DanMemoPlayer.exe` and the `_internal` folder, keep your `work` folder; no rebuild needed.

See the README for details.

---

**DanMemoPlayer-windows.zip** — Windows app, no Python needed.

1. Unzip and run `DanMemoPlayer.exe`. A setup page opens in your browser.
2. Choose the global APK (`com.eu.danmemo_2023-12-22.apk`) or the JP memorial app's `.xapk`, paste the folder of your extracted app-data backup, and click Build. It takes a few minutes, plus the optional download (~1.6 GB) of what the backup lacks.
3. Open the player. Next time the exe opens the player directly.

The exe isn't signed, so Windows SmartScreen may warn on first run ("More info" → "Run anyway"). Adding the `work` folder to Windows Defender's exclusions speeds up the build. See `README.txt` in the zip.

No game data or keys are included: you need your own copy of the game data. Keys, decrypted data and the player's data stay on your device (the `work` folder on Windows, the app's private storage on Android); don't share them.

---

**中文**：v1.1.0 新增 **Android 版**（`DanMemoPlayer-android.apk`，Android 7.0 以上、64 位元），不用電腦就能在手機上建置和播放；App 內附 LGPL ffmpeg，過場影片也在手機上轉換。

1. 把解壓好的 App 資料備份放到手機。在 Pixel 10 Pro 上用手機解壓 RAR 約需 2 小時 10 分，因為 Android 要逐一處理約 26 萬個檔案。加速方法：解壓 App 的電池設為「不受限制」、螢幕亮著並留在前景、暫停 Play 商店自動更新，並在目的資料夾放一個空的 `.nomedia` 檔以免相簿被塞滿。也可以在電腦上解壓後，用 USB 複製 `contents` 資料夾。
2. 安裝並開啟 App，允許「管理所有檔案」（只用來讀取備份），選擇國際版 APK（或日版紀念版的 `.xapk`）和備份資料夾，按「開始建置」。約需 15〜25 分鐘（Pixel 10 Pro 約 16 分、Pixel 5 約 24 分），勾選補下載（約 1.6 GB）的話另外加上下載時間。熄螢幕時建置仍會繼續，只是較慢。
3. 開啟播放器。「螢幕常亮」（播放劇情時／一律／關閉）在播放器的設定裡。

Windows 版：設定頁加上和播放器共用的語言選單，播放器工具列也能適應較窄的視窗。**從 v1.0.x 更新**：用新的 `DanMemoPlayer.exe` 和 `_internal` 資料夾取代舊的，保留 `work` 資料夾即可，不必重新建置。exe 沒有數位簽章，第一次執行時 Windows 可能跳出警告，按「其他資訊」→「仍要執行」。本程式不含任何遊戲資料或金鑰；產生的資料都留在你的裝置上，請勿分享。

**日本語**：v1.1.0 で **Android 版**（`DanMemoPlayer-android.apk`、Android 7.0 以上の 64 ビット端末）を追加しました。パソコンなしで端末上で作成・再生できます。アプリに LGPL の ffmpeg が入っているので、ムービーも端末上で変換されます。

1. 展開したアプリデータのバックアップを端末に置きます。Pixel 10 Pro で RAR を端末上で展開すると約 2 時間 10 分かかりました（約 26 万ファイルを Android が 1 つずつ処理するため）。速くするには、展開アプリの電池の使用を「制限なし」にし、画面をつけたまま前面に置き、Play ストアの自動更新を一時停止し、展開先に空の `.nomedia` ファイルを置いてギャラリーが埋まるのを防ぎます。パソコンで展開した `contents` フォルダを USB でコピーしても構いません。
2. アプリをインストールして開き、「すべてのファイルの管理を許可」をオンにして（バックアップを読むためだけに使います）、グローバル版 APK（またはメモリアル版の `.xapk`）とバックアップのフォルダを選び、「作成」を押します。15〜25 分ほどです（Pixel 10 Pro で約 16 分、Pixel 5 で約 24 分）。ダウンロード（約 1.6 GB）を選んだ場合はその時間が加わります。画面オフでも作成は続きますが、遅くなります。
3. プレイヤーを開きます。「画面を常にオン」（再生中／常に／しない）はプレイヤーの設定にあります。

Windows 版：設定ページにプレイヤーと共通の言語メニューを追加し、プレイヤーのツールバーが狭いウィンドウにも収まるようになりました。**v1.0.x からの更新**：新しい `DanMemoPlayer.exe` と `_internal` フォルダで置き換え、`work` フォルダは残してください。作り直す必要はありません。exe は署名されていないため、初回に Windows の警告が出ることがあります（「詳細情報」→「実行」）。ゲームデータや鍵は含まれていません。作成したデータは端末に残るので、共有しないでください。
