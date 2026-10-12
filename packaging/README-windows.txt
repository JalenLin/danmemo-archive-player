DanMemo Archive Player (Windows)
================================

[中文]
1. 解壓這個 zip，雙擊 DanMemoPlayer.exe。會開一個黑色視窗（記錄）和瀏覽器的設定頁。
2. 在設定頁：
   - APK：選擇國際版 APK（com.eu.danmemo_2023-12-22.apk，和社群資料備份一起分享的那份），
     或日版紀念版的 .xapk。
   - 備份資料夾：貼上解壓好的 App 資料備份所在路徑（裡面有 contents/1 … contents/8）。
     如果手上是 contents.part1.rar … part6.rar，先用 7-Zip 或 WinRAR 解壓。
   - 按「開始建置」。不含下載約幾分鐘；可勾選從遊戲 CDN 補下載缺少的素材（約 1.6 GB，時間看網速）。
3. 完成後按「開啟播放器」。之後再開 DanMemoPlayer.exe 會直接進播放器。關掉黑色視窗就結束。
也可以不用設定頁：把 APK 和解壓好的備份放進 exe 旁邊的 data 資料夾，程式會自己找到。
產生的金鑰、解密資料和播放器資料都在 work 資料夾，只留在這台電腦。不要分享 work 資料夾。
建置會寫出上萬個小檔案，Windows Defender 逐一掃描會讓它慢很多；可以在「Windows 安全性 → 病毒與威脅防護 → 排除項目」加入 work 資料夾。

[English]
1. Unzip and double-click DanMemoPlayer.exe. A log window and a setup page in your browser open.
2. On the setup page:
   - APK: choose the global APK (com.eu.danmemo_2023-12-22.apk, shared with the community data backup),
     or the JP memorial app's .xapk.
   - Backup folder: paste the path of the extracted app-data backup (it holds contents/1 ... contents/8).
     If you have contents.part1.rar ... part6.rar, extract them with 7-Zip or WinRAR first.
   - Click Build. It takes a few minutes, plus the optional download of what the backup lacks (~1.6 GB).
3. Then click "Open the player". Next time DanMemoPlayer.exe opens the player directly. Close the log
   window to stop. Alternatively put the APK and the extracted backup in the "data" folder next to the exe.
Keys, decrypted data and the player's data are written to the "work" folder and stay on this computer.
Don't share the work folder.
The build writes tens of thousands of small files; Windows Defender scanning each one slows it down a lot.
Adding the work folder to Defender's exclusions (Windows Security > Virus & threat protection > Exclusions) helps.

[日本語]
1. zip を展開して DanMemoPlayer.exe をダブルクリック。ログの画面とブラウザの設定ページが開きます。
2. 設定ページで：APK（グローバル版 com.eu.danmemo_2023-12-22.apk、またはメモリアル版の .xapk）を選び、
   展開したアプリデータのバックアップのフォルダ（contents/1 … contents/8 があるもの）のパスを貼り付け、
   「作成」を押します。作成は数分ほど（ダウンロードする場合はその時間が加わります）。
3. 完了したら「プレイヤーを開く」。次回からはプレイヤーが直接開きます。ログの画面を閉じると終了します。

No game data or keys are included: you bring your own. Code: MIT License (LICENSE). Game content belongs to
its owners. ffmpeg (_internal/ffmpeg) is a separate program under its own license (LICENSE.txt there).
Some antivirus tools flag unsigned PyInstaller programs by mistake; the source is at
https://github.com/JalenLin/danmemo-archive-player
