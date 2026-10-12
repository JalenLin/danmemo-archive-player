**DanMemoPlayer-windows.zip** — Windows app, no Python needed.

1. Unzip and run `DanMemoPlayer.exe`. A setup page opens in your browser.
2. Choose the global APK (`com.eu.danmemo_2023-12-22.apk`) or the JP memorial app's `.xapk`, paste the folder of your extracted app-data backup, and click Build. It takes a few minutes, plus the optional download (~1.6 GB) of what the backup lacks.
3. Open the player. Next time the exe opens the player directly.

The exe isn't signed, so Windows SmartScreen may warn on first run ("More info" → "Run anyway"). Adding the `work` folder to Windows Defender's exclusions speeds up the build. See `README.txt` in the zip.

**DanMemoPlayer-android.apk** — Android app (Android 7.0+, 64-bit), no computer needed. Put the global APK and the extracted backup (`contents`) in a `DanMemo` folder in the phone's storage, open the app, allow "manage all files", tap Build (decryption takes about 5–10 minutes). See the README.

No game data or keys are included: you need your own copy of the game data. Keys, decrypted data and the player's data stay in the `work` folder on your computer; don't share it.

---

**中文**：解壓後執行 `DanMemoPlayer.exe`，在開啟的頁面選擇國際版 APK（或日版紀念版的 `.xapk`），貼上解壓好的 App 資料備份資料夾，按「開始建置」。不含下載約幾分鐘。Android 版：把 APK 和解壓好的 `contents` 放進手機儲存空間的 `DanMemo` 資料夾，開啟 App、允許「管理所有檔案」後按建置。exe 沒有數位簽章，第一次執行時 Windows 可能跳出警告，按「其他資訊」→「仍要執行」。本程式不含任何遊戲資料或金鑰，需要自己準備；產生的資料都留在 `work` 資料夾，請勿分享。

**日本語**：展開して `DanMemoPlayer.exe` を実行し、開いたページでグローバル版 APK（またはメモリアル版の `.xapk`）を選び、展開したアプリデータのバックアップのフォルダを貼り付けて「作成」を押します。ダウンロードなしなら数分です。Android 版：APK と展開した `contents` を端末の `DanMemo` フォルダに入れ、アプリで「すべてのファイルの管理」を許可して「作成」。exe は署名されていないため、初回に Windows の警告が出ることがあります（「詳細情報」→「実行」）。ゲームデータや鍵は含まれていません。作成したデータは `work` フォルダに残ります。共有しないでください。
