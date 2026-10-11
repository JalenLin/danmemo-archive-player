"""Derive DanMemo asset keys from the game's own libapp.so (no keys are shipped with this project).

Usage: python tools/keys.py <path/to/libapp.so> [sample.enc]
Writes keys.json next to the project root. Each key is rebuilt the same way the game does it at
runtime: key[i] = T[S[i] ^ a] ^ b, with S/T tables inside libapp.so (see docs/PROCESS.md).
Offsets below are for the JP offline build 15.7.2 (com.danmemo); other builds need new offsets.
"""
import json
import os
import sys
import zlib

from elftools.elf.elffile import ELFFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name: (S table vaddr, length, T table vaddr, xor_a, xor_b)
LAYOUTS = {
    "jp-offline-15.7.2": {
        "aes_key": (0x1BBD0EC, 32, 0x1BBD20C, 0xCB, 0xD7),
        "aes_iv": (0x1BAE580, 16, 0x1BAFC26, 0x4E, 0xCF),
        "xxtea_key": (0x1BBAB50, 16, 0x1BBB86C, 0x44, 0xF6),
    },
}


def derive(lib, layout):
    data = open(lib, "rb").read()
    segs = [(s["p_vaddr"], s["p_offset"], s["p_filesz"]) for s in ELFFile(open(lib, "rb")).iter_segments()
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
    return out


def check(keys, sample):
    from Crypto.Cipher import AES
    d = open(sample, "rb").read()
    p = AES.new(keys["aes_key"].encode("latin-1"), AES.MODE_CBC, keys["aes_iv"].encode("latin-1")).decrypt(d)
    zlib.decompress(p[: -p[-1]])


def main():
    lib = sys.argv[1]
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
