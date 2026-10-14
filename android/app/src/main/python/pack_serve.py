"""A pack (tools/dmpack.py, *.dmpack in the user's folder): a zip of the player built on a computer and the assets
it uses, at the paths the player asks for. Serve them straight from there: media are stored uncompressed, so they
are read at their offset in the pack (with Range for seeking); the rest is inflated."""
import http.server
import os
import socket
import threading
import zipfile
from urllib.parse import unquote

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
         ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".ogg": "audio/ogg", ".mp4": "video/mp4",
         ".lwf": "application/octet-stream", ".svg": "image/svg+xml", ".woff2": "font/woff2"}
FILES = {}  # web path -> (fd, zipfile, info)
READY = threading.Event()
PLAYER = ""  # the app's own player files (html/js/css/vendor): they win over the pack's copy, like copy_player


def index(apks):
    for apk in apks:
        fd = os.open(apk, os.O_RDONLY)
        z = zipfile.ZipFile(apk)
        for i in z.infolist():
            if not i.is_dir():
                FILES[i.filename] = (fd, z, i)
    print(f"pack: {len(FILES)} files in {len(apks)} pack(s)", flush=True)
    READY.set()


def data_offset(fd, info):
    head = os.pread(fd, 30, info.header_offset)  # local file header: name and extra lengths at 26 and 28
    return info.header_offset + 30 + int.from_bytes(head[26:28], "little") + int.from_bytes(head[28:30], "little")


class Handler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET(body=False)

    def do_GET(self, body=True):
        READY.wait()
        path = unquote(self.path.split("?")[0].split("#")[0]).lstrip("/") or "index.html"
        if path.endswith("/"):
            path += "index.html"
        if PLAYER and not path.startswith(("data/", "r/")):  # an app update fixes the player without a new pack
            own = os.path.normpath(os.path.join(PLAYER, path))
            if own.startswith(PLAYER + os.sep) and os.path.isfile(own):
                with open(own, "rb") as f:
                    data = f.read()
                self.send_response(200)
                self._headers(path, TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream"), len(data))
                if body:
                    self.wfile.write(data)
                return
        hit = FILES.get(path)
        if not hit:
            return self.send_error(404)
        fd, z, info = hit
        ctype = TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
        if info.compress_type != zipfile.ZIP_STORED:  # data files: small enough to inflate whole
            data = z.read(info)
            self.send_response(200)
            self._headers(path, ctype, len(data))
            if body:
                self.wfile.write(data)
            return
        size, start = info.file_size, 0
        end = size - 1
        rng = self.headers.get("Range", "")
        if rng.startswith("bytes="):
            a, _, b = rng[6:].split(",")[0].partition("-")
            start = int(a) if a else max(0, size - int(b or 0))
            end = min(int(b), size - 1) if a and b else size - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        self._headers(path, ctype, end - start + 1)
        if not body:
            return
        pos, left = data_offset(fd, info) + start, end - start + 1
        try:
            while left > 0:
                buf = os.pread(fd, min(1 << 18, left), pos)
                if not buf:
                    break
                self.wfile.write(buf)
                pos += len(buf); left -= len(buf)
        except (BrokenPipeError, ConnectionResetError):  # the player dropped a request (seeking, skipping)
            pass

    def _headers(self, path, ctype, length):
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        # a new install replaces the splits: revalidate the app and its data, keep the media cached
        if path.endswith((".js", ".css", ".json", ".html")):
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()

    def log_message(self, *a):
        pass


def free_port(start):
    for p in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 0


def start(apks, player=""):
    global PLAYER
    PLAYER = os.path.normpath(player) if player and os.path.isdir(player) else ""
    port = free_port(18080)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=index, args=(apks,), name="danmemo-pack-index", daemon=True).start()  # listen first
    threading.Thread(target=srv.serve_forever, name="danmemo-server", daemon=True).start()
    return port
