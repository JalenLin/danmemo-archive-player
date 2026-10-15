**v1.3.0 — subtitles in two languages; the right voice for each story**

- **Subtitles in two languages (optional):** the JP and the global backups each hold one language. Choose the other one as "Second-language backup" on the setup page and rebuild: the player's Settings then offer a main and a second subtitle language, the second one smaller under the line, typed out along with it (also on narration, choices and the log). Names follow the main language; Settings also choose whether the text box fits each line, or keeps one height (the few lines too long for it get smaller type). With one language nothing changes and the choice doesn't appear. About 300 events the global client never ran have no English: a line missing in a language shows in the other one (never the same line twice), and the player says so at the top. Packs for the Android app include the subtitles.
- **Voices:** some voice files exist in several story folders with different recordings, and which one a build used depended on the system (Windows and Linux list folders differently). Each story now uses its own copy: 162 lines play a different, correct recording; builds are the same on every system.
- **Edges:** a black screen no longer shows a thin line of the previous scene round the picture (it showed whenever the window or the phone scaled the stage by a fraction), and the game's movies (gacha openings, cutscenes, credits) no longer show dark lines above and below (padding rows the movies are coded with). The ★4 close-up before a card's reveal no longer shows a strip of the other crop or of the backdrop at its top and bottom.
- **Text box:** ruby no longer makes its row taller (rows keep even spacing, two rows with ruby fit like any two rows), a line of three rows makes the box a little taller instead of running into its bottom edge, and a very long English word breaks instead of running out of the box.
- **The setup page** is now a gear icon at the top right, apart from the story menu.
- **Packing** warns when cutscene movies are still .usm (not converted).
- **If you built with v1.0.0:** that version didn't convert the backup's own cutscene movies (the 5th anniversary and 6th anniversary movies, the gacha openings). Click Rebuild once (the movies are converted on the way), then pack again.

**Updating:** Windows — replace `DanMemoPlayer.exe` and the `_internal` folder, keep your `work` folder, and click Rebuild once for the voice fix. Android — install the new APK over the old one and rebuild (or pack again on the computer).

No game data or keys are included; packs hold your own game data, so keep them to your own devices.

---

**中文**：
- **雙字幕（選填）**：日版和國際版的備份各是一種語言。在設定頁的「第二語言的備份資料夾」選另一份備份，再重新建置，播放器的「設定」就能選主字幕和副字幕。副字幕用較小的字顯示在台詞下方，和主字幕同步打字，旁白、選項和對話記錄也一樣；角色名稱跟著主字幕的語言；「設定」裡也能選對話框高度要隨內容，還是固定（極少數放不下的句子會自動縮小字）。只有一種語言時，一切照舊，也不會出現這個選項。國際版沒推出過的活動約有 300 篇沒有英文：沒有某種語言的句子會改用另一種語言顯示，不會重複顯示同一句，播放器上方也會提示。打包給 Android App 時，字幕會一起打包。
- **語音**：有些語音檔在好幾個劇情資料夾裡各有一份，錄音內容不同，之前建置時用哪一份取決於作業系統（Windows 和 Linux 的資料夾順序不同）。現在每篇劇情都會用自己那一份：162 句改成正確的錄音，而且各系統的建置結果一致。
- **畫面邊緣**：黑畫面時四周不會再透出上一個場景的細邊（視窗或手機把畫面縮放成非整數倍時會出現）；遊戲影片（抽卡開場、過場影片、片尾名單）上下也不會再有黑線（影片編碼時的補邊）。UR（★4）卡登場前的角色特寫，上下也不會再露出另一段特寫或背景的細條。
- **對話框**：注音不再把那一行撐高（行距一致，兩行帶注音也和一般兩行一樣高）；三行的台詞會讓框稍微長高，不再擠到框的下緣；很長的英文單字也會換行，不會超出框外。
- **建置設定**改成右上角的齒輪圖示，和劇情選單分開。
- **打包**時，如果過場影片還是 .usm（沒有轉檔），會提醒你。
- **用 v1.0.0 建置過的話**：那一版不會轉換備份本身附帶的過場影片（5 週年、6 週年影片和抽卡開場）。請按一次「重新建置」，影片會在建置過程中轉好，再重新打包。

**更新方式**：Windows 用新的 `DanMemoPlayer.exe` 和 `_internal` 資料夾取代舊的，保留 `work` 資料夾，再按一次「重新建置」套用語音修正。Android 直接安裝新版 APK，再重新建置（或在電腦上重新打包）。

**日本語**：
- **二か国語字幕（任意）**：日本版とグローバル版のバックアップは、それぞれ別の言語です。設定ページの「第二言語のバックアップ」でもう一方を選んで作り直すと、プレイヤーの「設定」で主字幕と副字幕を選べます。副字幕はセリフの下に小さく、主字幕と一緒に一文字ずつ表示され、ナレーション、選択肢、バックログにも出ます。キャラクター名は主字幕の言語です。テキストボックスの高さはセリフに合わせるか一定にするかを「設定」で選べます（一定のとき、収まらないごく一部のセリフは文字が小さくなります）。言語が一つの場合は何も変わらず、この項目も表示されません。グローバル版で開催されなかったイベント約 300 本には英語がありません。ある言語がないセリフはもう一方の言語で表示され（同じセリフを二度表示しません）、プレイヤー上部にその旨が出ます。Android アプリ用にまとめると、字幕も一緒に入ります。
- **ボイス**：同じ名前のボイスファイルが複数のストーリーフォルダにあり、録音が違うものがあります。これまでどれを使うかは OS 次第でした（Windows と Linux でフォルダの並び順が違うため）。各ストーリーが自分のものを使うようにし、162 のセリフが正しい録音になりました。どの OS でも同じ結果になります。
- **画面の端**：暗転したとき、画面の周りに前の場面が細く見えることがなくなりました（ウィンドウや端末で画面が半端な倍率に縮小されると出ていました）。ゲームのムービー（ガチャのオープニング、ムービー、エンドクレジット）の上下に出ていた黒い線（エンコード時の余白）も表示されなくなりました。★4 登場前のキャラクターのアップで、上下にもう一方のカットや背景が細く見えることもなくなりました。
- **テキストボックス**：ルビで行の高さが変わらなくなりました（行間がそろい、ルビのある 2 行もふつうの 2 行と同じ高さ）。3 行のセリフは枠の下端に食い込まず、枠が少し高くなります。とても長い英単語も枠からはみ出さずに折り返します。
- **セットアップ**はストーリーのメニューから離して、右上の歯車アイコンにしました。
- **まとめる**とき、ムービーが .usm のまま（未変換）なら知らせます。
- **v1.0.0 で作成した場合**：そのバージョンはバックアップ自体のムービー（5 周年・6 周年ムービー、ガチャのオープニング）を変換しませんでした。一度「作り直す」を押すと変換されるので、そのあとでまとめ直してください。

**更新方法**：Windows は新しい `DanMemoPlayer.exe` と `_internal` フォルダで置き換え、`work` フォルダは残して、ボイスの修正のために一度「作り直す」を押してください。Android は新しい APK をインストールして作り直してください（またはパソコンでまとめ直してください）。
