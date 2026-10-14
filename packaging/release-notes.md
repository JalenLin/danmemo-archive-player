**v1.2.1 — packing on Windows: faster, and easier to find**

- **"Pack for the Android app" is easier to find:** after the first build the exe opens the player directly, so the setup page (and its pack button) was out of reach. The player's menu now has **Setup**, which leads back to it (also to rebuild).
- **Faster packing:** Windows Defender scans every file as it is opened, and packing reads ~200,000 of them. They are now read ahead in parallel. Adding both the `work` folder and the backup folder to Defender's exclusions speeds it up further.
- The pack holds only the player's own files and the assets the stories use (no development files).

**Updating:** Windows — replace `DanMemoPlayer.exe` and the `_internal` folder, keep your `work` folder; no rebuild needed. Android — install the new APK over the old one; a pack made with v1.2.0 keeps working.

See v1.2.0 for packing on a computer and playing on the phone. No game data or keys are included; the pack holds your own game data, so keep it to your own devices.

---

**中文**：
- **更容易找到「打包給 Android App」**：第一次建置後，exe 會直接開啟播放器，所以之前找不到設定頁和打包按鈕。現在播放器的選單多了「建置設定」，可以回到設定頁打包或重新建置。
- **打包變快**：Windows Defender 會在每個檔案被開啟時掃描，而打包要讀約 20 萬個檔案。現在改成平行預讀。把 `work` 和備份資料夾都加入 Defender 的排除項目會更快。
- 打包檔只收播放器本身和劇情用到的素材，不含開發用檔案。

**更新方式**：Windows 用新的 `DanMemoPlayer.exe` 和 `_internal` 資料夾取代舊的，保留 `work` 資料夾，不必重新建置。Android 直接安裝新版 APK 覆蓋，用 v1.2.0 做的打包檔可以繼續使用。

**日本語**：
- **「Android アプリ用にまとめる」が見つけやすくなりました**：初回の作成後は exe がプレイヤーを直接開くため、設定ページ（とまとめるボタン）に戻れませんでした。プレイヤーのメニューに「セットアップ」を追加し、設定ページに戻ってまとめたり作り直したりできます。
- **まとめるのが速くなりました**：Windows Defender はファイルを開くたびにスキャンし、まとめる処理は約 20 万ファイルを読みます。並列で先読みするようにしました。`work` フォルダとバックアップのフォルダを Defender の除外に入れるとさらに速くなります。
- パックにはプレイヤー本体とストーリーで使う素材だけが入ります（開発用ファイルは入りません）。

**更新方法**：Windows は新しい `DanMemoPlayer.exe` と `_internal` フォルダで置き換え、`work` フォルダは残してください（作り直し不要）。Android は新しい APK をそのままインストールしてください。v1.2.0 で作ったパックもそのまま使えます。
