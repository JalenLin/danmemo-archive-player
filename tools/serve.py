"""Local static server for web/ with HTTP Range support (audio/video seeking).

Usage: python tools/serve.py [port] [host]   (default 8080 127.0.0.1; use host 0.0.0.0 for LAN access)
"""
import http.server
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import config
    WEB = config.load()["web"]
except SystemExit:  # no config.json yet: serve the bundled player
    WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".ogg": "audio/ogg", ".webp": "image/webp", ".json": "application/json",
                      ".lwf": "application/octet-stream", ".mp4": "video/mp4", ".js": "text/javascript"}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB, **kw)

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else max(0, size - int(m.group(2)))
        end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        end = min(end, size - 1)
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        rem = getattr(self, "_remaining", None)
        if rem is None:
            return super().copyfile(source, outputfile)
        while rem > 0:
            buf = source.read(min(65536, rem))
            if not buf:
                break
            outputfile.write(buf)
            rem -= len(buf)

    def end_headers(self):
        # app code and data change while developing: always revalidate them (assets can be cached)
        if self.path.split("?")[0].endswith((".js", ".css", ".json", ".html", "/")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    print(f"Serving {os.path.abspath(WEB)} at http://{host}:{port}/", flush=True)
    http.server.ThreadingHTTPServer((host, port), Handler).serve_forever()
