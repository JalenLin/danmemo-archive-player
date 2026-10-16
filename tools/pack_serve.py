"""A pack (tools/dmpack.py): a zip of the player built on a computer and the assets it uses, at the paths the
player asks for. Played as it is: by the Android app (*.dmpack in the user's folder) and by the launcher on a
computer (a pack given on the command line, or one next to the program when nothing is built there). Media are
stored uncompressed, so they are read at their offset in the pack (with Range for seeking); the rest is inflated."""
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
LOCKS = {}  # fd -> lock, where there is no os.pread (Windows): one file position per pack, so reads take turns


def choose(packs):
    """the pack to play: the one made or copied last. Each pack holds a whole player, so two of them (JP and
    global, an older build) are never mixed."""
    return max(packs, key=os.path.getmtime) if packs else None


def index(pack):
    fd = os.open(pack, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    LOCKS[fd] = threading.Lock()
    z = zipfile.ZipFile(pack)
    for i in z.infolist():
        if not i.is_dir():
            FILES[i.filename] = (fd, z, i)
    print(f"pack: {len(FILES)} files in {pack}", flush=True)
    READY.set()


def load(packs, player=""):
    """index the chosen pack in the background (the server answers once it is ready); returns the pack"""
    global PLAYER
    PLAYER = os.path.normpath(player) if player and os.path.isdir(player) else ""
    pack = choose(packs)
    threading.Thread(target=index, args=(pack,), name="danmemo-pack-index", daemon=True).start()
    return pack


def pread(fd, n, pos):
    if hasattr(os, "pread"):
        return os.pread(fd, n, pos)
    with LOCKS[fd]:
        os.lseek(fd, pos, os.SEEK_SET)
        return os.read(fd, n)


def data_offset(fd, info):
    head = pread(fd, 30, info.header_offset)  # local file header: name and extra lengths at 26 and 28
    return info.header_offset + 30 + int.from_bytes(head[26:28], "little") + int.from_bytes(head[28:30], "little")


def send(h, body=True):
    """answer the GET (or HEAD) of the request handler h from the pack"""
    READY.wait()
    path = unquote(h.path.split("?")[0].split("#")[0]).lstrip("/") or "index.html"
    if path.endswith("/"):
        path += "index.html"
    if PLAYER and not path.startswith(("data/", "r/")):  # an app update fixes the player without a new pack
        own = os.path.normpath(os.path.join(PLAYER, path))
        if own.startswith(PLAYER + os.sep) and os.path.isfile(own):
            with open(own, "rb") as f:
                data = f.read()
            h.send_response(200)
            headers(h, path, TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream"), len(data))
            if body:
                h.wfile.write(data)
            return
    hit = FILES.get(path)
    if not hit:
        return h.send_error(404)
    fd, z, info = hit
    ctype = TYPES.get(os.path.splitext(path)[1].lower(), "application/octet-stream")
    if info.compress_type != zipfile.ZIP_STORED:  # data files: small enough to inflate whole
        data = z.read(info)
        h.send_response(200)
        headers(h, path, ctype, len(data))
        if body:
            h.wfile.write(data)
        return
    size, start = info.file_size, 0
    end = size - 1
    rng = h.headers.get("Range", "")
    if rng.startswith("bytes="):
        a, _, b = rng[6:].split(",")[0].partition("-")
        start = int(a) if a else max(0, size - int(b or 0))
        end = min(int(b), size - 1) if a and b else size - 1
        h.send_response(206)
        h.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    else:
        h.send_response(200)
    headers(h, path, ctype, end - start + 1)
    if not body:
        return
    pos, left = data_offset(fd, info) + start, end - start + 1
    try:
        while left > 0:
            buf = pread(fd, min(1 << 18, left), pos)
            if not buf:
                break
            h.wfile.write(buf)
            pos += len(buf); left -= len(buf)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):  # the player dropped a request (seeking, skipping)
        pass


def headers(h, path, ctype, length):
    h.send_header("Content-Type", ctype)
    h.send_header("Content-Length", str(length))
    h.send_header("Accept-Ranges", "bytes")
    # a new install replaces the splits: revalidate the app and its data, keep the media cached
    if path.endswith((".js", ".css", ".json", ".html")):
        h.send_header("Cache-Control", "no-cache")
    h.end_headers()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        send(self, body=False)

    def do_GET(self):
        send(self)

    def log_message(self, *a):
        pass


def free_port(start):
    for p in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return 0


def start(packs, player=""):
    """the Android app: serve the pack on its own server; returns the port"""
    port = free_port(18080)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    load(packs, player)  # listen first, index in the background
    # nothing stops the server: wake rarely (the default 0.5 s poll keeps waking the phone in the background)
    threading.Thread(target=srv.serve_forever, args=(3600,), name="danmemo-server", daemon=True).start()
    return port
