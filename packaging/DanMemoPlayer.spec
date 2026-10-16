# PyInstaller spec for the Windows app: pyinstaller packaging/DanMemoPlayer.spec
# One folder (DanMemoPlayer.exe + _internal); the tools are shipped as source and imported at run time by
# tools/launcher.py, so their third-party imports are listed here. No keys or game data are included.
import glob, os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
datas = [(f, "tools") for f in glob.glob(os.path.join(ROOT, "tools", "*.py")) + [os.path.join(ROOT, "tools", "launcher.html")]]
for f in glob.glob(os.path.join(ROOT, "web", "**", "*"), recursive=True):
    rel = os.path.relpath(f, ROOT)
    if os.path.isfile(f) and not rel.startswith(os.path.join("web", "data")) and not rel.startswith(os.path.join("web", "r")):
        datas.append((f, os.path.dirname(rel)))
datas += [(os.path.join(ROOT, "LICENSE"), ".")]

# the tools run from source at run time; listing them makes PyInstaller bundle their (standard library and
# third-party) imports too: ssl for the CDN downloads, math, csv, …
TOOL_MODULES = ["config", "keys", "dmcrypto", "fbdump", "decrypt_all", "build_web", "fill_gaps", "usm", "gachanames",
                "serve", "cardstat", "dmpack", "pack_serve"]
hidden = TOOL_MODULES + ["ssl", "math", "csv", "statistics", "email", "http.client"] + (collect_submodules("Crypto.Cipher") + collect_submodules("Crypto.Util") + collect_submodules("elftools")
          + ["numpy", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont", "PIL.ImageFilter", "PIL.PngImagePlugin",
             "PIL.JpegImagePlugin", "http.server", "concurrent.futures", "zipfile", "zlib", "tempfile", "runpy",
             "urllib.request", "urllib.error", "hashlib", "html", "struct", "bisect", "colorsys", "random"])

a = Analysis([os.path.join(ROOT, "tools", "launcher.py")], pathex=[os.path.join(ROOT, "tools")], datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "matplotlib", "IPython", "pytest"])
pyz = PYZ(a.pure)
# UTF-8 mode: open() defaults to UTF-8 instead of the Windows code page (cp950 / cp932 can't read the game's text)
exe = EXE(pyz, a.scripts, [("X utf8_mode=1", None, "OPTION")], exclude_binaries=True, name="DanMemoPlayer",
          console=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="DanMemoPlayer", upx=False)
