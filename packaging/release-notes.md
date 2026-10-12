**v1.0.1 — cutscene movies fixed** (Windows)

A build from an unmodified app-data backup had no cutscene movies: the backup ships them as `.usm` files, and v1.0.0 only converted movies downloaded from the CDN. Affected: the Movies page, nine cutscenes in the stories (the 6th-anniversary SO12 chapters and two 5th-anniversary PVs) and the gacha reveal's opening movie. v1.0.1 converts all of them in a new build step (about 10 seconds), leaving your backup untouched. The zip is also ~40 MB smaller (ffprobe isn't needed any more).

**Updating from v1.0.0:** replace `DanMemoPlayer.exe` and the `_internal` folder with the new ones, keep your `work` folder, start the program and click Rebuild (you can uncheck the download). The keys and decrypted data are reused.

---

**DanMemoPlayer-windows.zip** — Windows app, no Python needed.

1. Unzip and run `DanMemoPlayer.exe`. A setup page opens in your browser.
2. Choose the global APK (`com.eu.danmemo_2023-12-22.apk`) or the JP memorial app's `.xapk`, paste the folder of your extracted app-data backup, and click Build. It takes a few minutes, plus the optional download (~1.6 GB) of what the backup lacks.
3. Open the player. Next time the exe opens the player directly.

The exe isn't signed, so Windows SmartScreen may warn on first run ("More info" → "Run anyway"). Adding the `work` folder to Windows Defender's exclusions speeds up the build. See `README.txt` in the zip.

No game data or keys are included: you need your own copy of the game data. Keys, decrypted data and the player's data stay in the `work` folder on your computer; don't share it.

---

**中文**：v1.0.1 修正過場影片。用未經修改的 App 資料備份建置時，v1.0.0 沒有轉換備份裡的 `.usm` 影片，導致影片頁、9 段劇情過場（6 週年長篇 SO12 等）和抽卡演出的開場影片都缺少。新版會在建置時轉換全部影片（約 10 秒），不會修改你的備份；zip 也小了約 40 MB。**從 v1.0.0 更新**：用新的 `DanMemoPlayer.exe` 和 `_internal` 資料夾取代舊的，保留 `work` 資料夾，執行後按「重新建置」（可取消勾選補下載），金鑰和解密資料會沿用。使用方式：解壓後執行 `DanMemoPlayer.exe`，在開啟的頁面選擇國際版 APK（或日版紀念版的 `.xapk`），貼上解壓好的備份資料夾，按「開始建置」。exe 沒有數位簽章，第一次執行時 Windows 可能跳出警告，按「其他資訊」→「仍要執行」。本程式不含任何遊戲資料或金鑰；產生的資料都留在 `work` 資料夾，請勿分享。

**日本語**：v1.0.1 でムービーを修正しました。改変していないアプリデータのバックアップから作成すると、v1.0.0 はバックアップ内の `.usm` ムービーを変換せず、ムービーページ、シナリオ中の 9 本のムービー（6 周年長編 SO12 など）、ガチャ演出のオープニングが欠けていました。新版は作成時にすべて変換します（約 10 秒、バックアップは変更しません）。zip も約 40 MB 小さくなりました。**v1.0.0 からの更新**：新しい `DanMemoPlayer.exe` と `_internal` フォルダで置き換え、`work` フォルダは残したまま起動して「作り直す」を押してください（ダウンロードはオフで構いません）。鍵と復号データはそのまま使われます。exe は署名されていないため、初回に Windows の警告が出ることがあります（「詳細情報」→「実行」）。ゲームデータや鍵は含まれていません。
