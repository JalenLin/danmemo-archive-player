**v1.2.0 — pack on a computer, play on the phone**

New: with a computer, the Android app no longer needs the backup on the phone or a build there.

1. Build with the Windows app as before, then click **"Pack for the Android app"** on the setup page (from source: `python tools/dmpack.py`). It writes `DanMemo.dmpack` next to the exe: the player and only the assets the stories use (~8.7 GB for the global build).
2. Copy `DanMemo.dmpack` into the `DanMemo` folder of the phone's internal storage (USB, "File transfer"). One big file copies quickly: ~2 minutes on a Pixel 10 Pro, instead of the hours that ~260,000 small files take.
3. Open the app and allow "manage all files": it plays from the pack, with nothing to set up.

The pack holds your own game data: keep it to your own devices, don't share it. App updates bring the new player code without a new pack. Building on the phone, without a computer, works as before.

Android: the sound stops when you leave the app (home screen, another app) and goes on when you come back; AUTO waits meanwhile. The app also keeps the phone less busy in the background.

**Updating:** Android — install the new APK over the old one. Windows — replace `DanMemoPlayer.exe` and the `_internal` folder, keep your `work` folder; no rebuild needed.

---

**DanMemoPlayer-windows.zip** — Windows app, no Python needed.

1. Unzip and run `DanMemoPlayer.exe`. A setup page opens in your browser.
2. Choose the global APK (`com.eu.danmemo_2023-12-22.apk`) or the JP memorial app's `.xapk`, paste the folder of your extracted app-data backup, and click Build. It takes a few minutes, plus the optional download (~1.6 GB) of what the backup lacks.
3. Open the player. Next time the exe opens the player directly.

**DanMemoPlayer-android.apk** — Android 7.0 or later, 64-bit. Play from a pack made on a computer (above), or build on the phone: put the extracted backup on the phone, choose the APK and the backup folder in the app, and tap Build (~15–25 minutes). See the README.

The exe isn't signed, so Windows SmartScreen may warn on first run ("More info" → "Run anyway"). No game data or keys are included: you need your own copy of the game data. Keys, decrypted data and the player's data stay on your devices; don't share them.

---

**中文**：v1.2.0 新增「電腦打包」。有電腦的話，Android App 不用再把備份放進手機，也不用在手機上建置。

1. 照常用 Windows 版建置，再按設定頁的「打包給 Android App」（用原始碼的話執行 `python tools/dmpack.py`）。會在 exe 旁邊產生 `DanMemo.dmpack`，裡面只有播放器和劇情用到的素材，國際版約 8.7 GB。
2. 用 USB（檔案傳輸）把 `DanMemo.dmpack` 複製到手機內部儲存空間的 `DanMemo` 資料夾。只有一個大檔案，Pixel 10 Pro 約 2 分鐘；搬約 26 萬個小檔案則要好幾個小時。
3. 開啟 App，允許「管理所有檔案」，就會直接從打包檔播放，不用任何設定。

打包檔裡是你自己的遊戲資料，請只用在自己的裝置上，不要分享。App 更新後，播放器程式會自動用新版，不用重新打包。沒有電腦的話，照舊在手機上建置即可。

Android：離開 App（回桌面、切到其他 App）時聲音會停，回來後接著播放，AUTO 也會等你回來；在背景時也更省電。**更新方式**：Android 直接安裝新版 APK 覆蓋；Windows 用新的 `DanMemoPlayer.exe` 和 `_internal` 資料夾取代舊的，保留 `work` 資料夾，不必重新建置。本程式不含任何遊戲資料或金鑰。

**日本語**：v1.2.0 で「パソコンでまとめる」を追加しました。パソコンがあれば、Android アプリのためにバックアップを端末に移したり、端末で作成したりする必要はありません。

1. いつも通り Windows 版で作成し、設定ページの「Android アプリ用にまとめる」を押します（ソースからは `python tools/dmpack.py`）。exe の隣に `DanMemo.dmpack` ができます。中身はプレイヤーとストーリーで使う素材だけで、グローバル版なら約 8.7 GB です。
2. `DanMemo.dmpack` を USB（ファイル転送）で端末の内部ストレージの `DanMemo` フォルダにコピーします。大きなファイル 1 つなので Pixel 10 Pro で約 2 分でした（約 26 万の小さなファイルなら数時間かかります）。
3. アプリを開いて「すべてのファイルの管理を許可」をオンにすれば、パックからそのまま再生できます。

中身は自分のゲームデータです。自分の端末だけで使い、共有しないでください。アプリを更新するとプレイヤーのプログラムも新しくなるので、まとめ直す必要はありません。パソコンがない場合は、これまで通り端末上で作成できます。

Android：アプリを離れると（ホーム画面、別のアプリ）音が止まり、戻ると続きから再生します。その間 AUTO も待ちます。バックグラウンドでの電池消費も減りました。**更新方法**：Android は新しい APK をそのままインストール、Windows は新しい `DanMemoPlayer.exe` と `_internal` フォルダで置き換え、`work` フォルダは残してください（作り直し不要）。ゲームデータや鍵は含まれていません。
