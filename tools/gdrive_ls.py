"""List a public Google Drive folder via the embedded folder view (no auth). Usage: gdrive_ls.py <folder_id> [depth]"""
import html, re, sys, urllib.request

def ls(fid):
    s = urllib.request.urlopen(f"https://drive.google.com/embeddedfolderview?id={fid}", timeout=60).read().decode("utf-8")
    out = []
    for m in re.finditer(r'<a href="([^"]+)"[^>]*>.*?<div class="flip-entry-title">([^<]+)</div>', s, re.S):
        url, name = html.unescape(m.group(1)), html.unescape(m.group(2))
        mm = re.search(r"/folders/([\w-]+)", url) or re.search(r"/file/d/([\w-]+)", url)
        out.append((name, "dir" if "/folders/" in url else "file", mm.group(1)))
    return out

def walk(fid, depth, prefix=""):
    for name, kind, i in ls(fid):
        print(f"{prefix}{name}{'/' if kind == 'dir' else ''}\t{i}")
        if kind == "dir" and depth > 0:
            walk(i, depth - 1, prefix + name + "/")

if __name__ == "__main__":
    walk(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
