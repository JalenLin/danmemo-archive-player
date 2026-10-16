**v1.3.2 — packs play on a computer too**

- **Packs on a computer:** a `.dmpack` made with "Pack for the Android app" now also plays on a computer, e.g. one without the backup: drop it on `DanMemoPlayer.exe`, or put it next to the exe where nothing is built yet, and the player opens with nothing to set up. The setup page still opens from the player's Setup link and shows which pack is playing. From source: `python tools/launcher.py DanMemo.dmpack`.
- **Several packs:** with more than one pack in the phone's `DanMemo` folder, the app read them all as one, so the stories of one pack could come with the pictures of another. It now plays only the newest one (the one copied last); the computer does the same.

**Updating:** nothing to rebuild or pack again. Windows: replace `DanMemoPlayer.exe` and the `_internal` folder, keep your `work` folder. Android: install the new APK over the old one.

No game data or keys are included; packs hold your own game data, so keep them to your own devices.

---

**中文**：
- **電腦也能播放打包檔**：用「打包給 Android App」產生的 `.dmpack`，現在電腦也能直接播放，例如在另一台沒有備份的電腦上看。把它拖到 `DanMemoPlayer.exe` 上，或放在還沒建置過的 exe 旁邊，開啟後就直接播放，不用設定。從播放器的「設定」連結仍可開啟設定頁，頁面上會顯示正在播放哪個打包檔。用原始碼的話是 `python tools/launcher.py DanMemo.dmpack`。
- **多個打包檔**：手機的 `DanMemo` 資料夾裡放了好幾個打包檔時，App 原本會把它們全部合在一起讀取，可能出現劇情來自其中一個打包檔、圖片卻來自另一個的情況。現在只用最新的一個（最後複製進去的），電腦版也一樣。

**更新方式**：不用重新建置，也不用重新打包。Windows 用新的 `DanMemoPlayer.exe` 和 `_internal` 資料夾取代舊的，保留 `work` 資料夾。Android 直接安裝新版 APK。

**日本語**：
- **まとめたファイルをパソコンでも再生**：「Android アプリ用にまとめる」で作った `.dmpack` を、パソコンでもそのまま再生できるようになりました（バックアップのない別のパソコンなど）。`DanMemoPlayer.exe` にドロップするか、まだ作成していない exe の隣に置けば、設定なしでプレイヤーが開きます。プレイヤーの「設定」リンクから設定ページも開け、再生中のファイルが表示されます。ソースからは `python tools/launcher.py DanMemo.dmpack`。
- **複数のファイル**：端末の `DanMemo` フォルダにまとめたファイルが複数あると、アプリはすべてを一つとして読み込んでいたため、ストーリーと画像が別々のファイルから読み込まれることがありました。一番新しいもの（最後にコピーしたもの）だけを使うようにしました。パソコンでも同じです。

**更新方法**：作り直しもまとめ直しも不要です。Windows は新しい `DanMemoPlayer.exe` と `_internal` フォルダで置き換え、`work` フォルダは残してください。Android は新しい APK をインストールしてください。
