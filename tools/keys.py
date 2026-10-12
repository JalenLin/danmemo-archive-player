"""Derive DanMemo asset keys from the game's own libapp.so (no keys are shipped with this project).

Usage: python tools/keys.py <libapp.so | app.apk | app.xapk> [sample.enc]
Writes keys.json next to the project root. Each key is rebuilt the same way the game does it at
runtime: key[i] = T[S[i] ^ a] ^ b, with S/T tables inside libapp.so (see docs/PROCESS.md).
Known builds: the JP offline app 15.7.2 (com.danmemo, 64-bit libapp.so) and the global app of
2023-12-22 (com.eu.danmemo, the APK that comes with the community data backup; 32-bit libapp.so).
Both use the same keys. An .apk/.xapk is searched for lib/*/libapp.so.
"""
import io
import json
import os
import sys
import tempfile
import zipfile
import zlib

from elftools.elf.elffile import ELFFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name: (machine, {key: (S table vaddr, length, T table vaddr, xor_a, xor_b)})
LAYOUTS = {
    "jp-offline-15.7.2": ("EM_AARCH64", {
        "aes_key": (0x1BBD0EC, 32, 0x1BBD20C, 0xCB, 0xD7),
        "aes_iv": (0x1BAE580, 16, 0x1BAFC26, 0x4E, 0xCF),
        "xxtea_key": (0x1BBAB50, 16, 0x1BBB86C, 0x44, 0xF6),
    }),
    # global 2023-12-22, armeabi-v7a (Thumb code): master loader 0x143ec06 (AES key), 0x14394bc (XXTEA),
    # API code 0x140884e (IV); same loop as the JP build, other tables and xor constants
    "global-2023-12-22": ("EM_ARM", {
        "aes_key": (0x260D1C0, 32, 0x28C26B8, 0x42, 0x6E),
        "aes_iv": (0x28B9220, 16, 0x28B91A0, 0xA8, 0xDB),
        "xxtea_key": (0x28B9230, 16, 0x28C21C4, 0x1F, 0x9A),
    }),
}


def open_lib(path):
    """libapp.so itself, or extracted from an .apk / .xapk (which nests the split APKs)"""
    if not zipfile.is_zipfile(path):
        return path
    def find(z):
        names = [n for n in z.namelist() if n.endswith("/libapp.so")]
        for arch in ("arm64-v8a", "armeabi-v7a"):
            for n in names:
                if f"/{arch}/" in n:
                    return z.read(n)
        for n in z.namelist():
            if n.endswith(".apk"):
                r = find(zipfile.ZipFile(io.BytesIO(z.read(n))))
                if r:
                    return r
        return None
    data = find(zipfile.ZipFile(path))
    if not data:
        sys.exit(f"no libapp.so inside {path}")
    tmp = tempfile.NamedTemporaryFile(suffix=".so", delete=False)
    tmp.write(data); tmp.close()
    return tmp.name


def derive(lib, layout):
    machine, layout = layout
    data = open(lib, "rb").read()
    elf = ELFFile(open(lib, "rb"))
    if elf["e_machine"] != machine:
        raise ValueError(f"{elf['e_machine']} library")
    segs = [(s["p_vaddr"], s["p_offset"], s["p_filesz"]) for s in elf.iter_segments()
            if s["p_type"] == "PT_LOAD"]

    def at(va, n):
        for v, o, fs in segs:
            if v <= va < v + fs:
                return data[o + va - v: o + va - v + n]
        raise ValueError(hex(va))

    out = {}
    for name, (s_va, n, t_va, a, b) in layout.items():
        S, T = at(s_va, n), at(t_va, 256)
        out[name] = bytes(T[x ^ a] ^ b for x in S).decode("latin-1")
    # every .enc starts with the same block, which only decrypts to zlib (78 9C) with an IV beginning "uR"
    # (docs/PROCESS.md); a wrong layout gives something else
    if not out["aes_iv"].startswith("uR"):
        raise ValueError("tables don't give the known IV")
    return out


def check(keys, sample):
    from Crypto.Cipher import AES
    d = open(sample, "rb").read()
    p = AES.new(keys["aes_key"].encode("latin-1"), AES.MODE_CBC, keys["aes_iv"].encode("latin-1")).decrypt(d)
    zlib.decompress(p[: -p[-1]])


def main():
    lib = open_lib(sys.argv[1])
    sample = sys.argv[2] if len(sys.argv) > 2 else None
    for name, layout in LAYOUTS.items():
        try:
            keys = derive(lib, layout)
            if sample:
                check(keys, sample)
        except Exception as e:
            print(f"{name}: no match ({e})")
            continue
        json.dump({"layout": name, **keys}, open(os.path.join(ROOT, "keys.json"), "w"))
        print(f"keys.json written ({name})")
        return 0
    print("No known layout matched this libapp.so.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
