"""Entry point the Android app calls (MainActivity.kt): start tools/launcher.py's server in a background thread
and return its port. The app has unpacked tools/ and web/ into `app_dir` (a real folder: the launcher serves
web/ from disk); `home` gets work/ (keys, decrypted data, the player's data); `data` is the folder in shared
storage where the user puts the APK and the extracted backup."""
import os
import sys
import threading
import warnings


def start(app_dir, home, data, ffmpeg=""):
    # Chaquopy shows ResourceWarning / DeprecationWarning (fork in a threaded process): noise in the build log
    warnings.simplefilter("ignore", ResourceWarning)
    warnings.simplefilter("ignore", DeprecationWarning)
    sys.__stdout__ = sys.stdout  # the launcher echoes its log there: logcat (python.stdout)
    os.environ.update(DANMEMO_APP=app_dir, DANMEMO_HOME=home, DANMEMO_DATA=data,
                      DANMEMO_INPROCESS="1", DANMEMO_NO_BROWSER="1")
    if ffmpeg and os.path.isfile(ffmpeg):  # the app's own ffmpeg (lib/<abi>/libffmpeg.so): the cutscene movies
        os.environ["DANMEMO_FFMPEG"] = ffmpeg
    tools = os.path.join(app_dir, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import launcher
    port = launcher.free_port(18080)
    os.environ["DANMEMO_PORT"] = str(port)
    threading.Thread(target=launcher.main, name="danmemo-server", daemon=True).start()
    return port
