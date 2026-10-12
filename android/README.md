# Android app

A thin shell around the same Python code the Windows app runs: Chaquopy runs `tools/launcher.py` inside the app
(`app/src/main/python/android_main.py` starts it), and a full-screen WebView shows the setup page and then the
player on `127.0.0.1`. `tools/` and `web/` are copied into the APK's assets at build time and unpacked to the
app's files on first start (and after each update).

On the phone the launcher runs each build step in-process (no child processes on Android) and decrypts with a
few forked workers (`decrypt_all.py`: Python's multiprocessing doesn't work there). The user's data is read from
`/sdcard/DanMemo` (all-files access); keys, decrypted data and the player's data stay in the app's private storage.

Build (needs the Android SDK, JDK 17 and Python 3.12 — Chaquopy installs the pip packages with it):

    cd android
    ./gradlew assembleDebug        # app/build/outputs/apk/debug/app-debug.apk

Release builds are signed from the environment (`DANMEMO_KEYSTORE`, `DANMEMO_KEYSTORE_PASSWORD`,
`DANMEMO_KEY_ALIAS`, `DANMEMO_KEY_PASSWORD`); `.github/workflows/release.yml` sets them from repository secrets.
