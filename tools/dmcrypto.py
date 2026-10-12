"""DanMemo offline (15.7.2) asset decryption.

.enc file = AES-256-CBC(zlib(flatbuffer)), PKCS#7 padded.
String fields inside the flatbuffer are XXTEA-encrypted.
Keys are read from keys.json, produced by tools/keys.py from the game's own libapp.so.
"""
import json
import os
import struct
import zlib

from Crypto.Cipher import AES

_DELTA = 0x9E3779B9
_KEYS = None


def keys():
    """(aes key, aes iv, xxtea key words), read from keys.json on first use, not on import: the launcher
    imports the tools before the keys step has written the file"""
    global _KEYS
    if _KEYS is None:
        k = json.load(open(os.environ.get("DANMEMO_KEYS")
                           or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "keys.json"),
                           encoding="utf-8"))
        _KEYS = (k["aes_key"].encode("latin-1"), k["aes_iv"].encode("latin-1"),
                 struct.unpack("<4I", k["xxtea_key"].encode("latin-1")))
    return _KEYS


def decrypt_file(data: bytes) -> bytes:
    aes_key, aes_iv, _ = keys()
    p = AES.new(aes_key, AES.MODE_CBC, aes_iv).decrypt(data)
    p = p[: -p[-1]]
    return zlib.decompress(p)


def xxtea_decrypt_words(v):
    n = len(v)
    if n < 2:
        return v
    rounds = 6 + 52 // n
    _K = keys()[2]
    s = (rounds * _DELTA) & 0xFFFFFFFF
    y = v[0]
    while rounds:
        e = (s >> 2) & 3
        for p in range(n - 1, -1, -1):
            z = v[p - 1] if p > 0 else v[n - 1]
            mx = (((z >> 5) ^ (y << 2)) + ((y >> 3) ^ (z << 4))) ^ ((s ^ y) + (_K[(p & 3) ^ e] ^ z))
            v[p] = (v[p] - mx) & 0xFFFFFFFF
            y = v[p]
        s = (s - _DELTA) & 0xFFFFFFFF
        rounds -= 1
    return v


def xxtea_decrypt(data: bytes) -> bytes:
    n = len(data) // 4
    v = list(struct.unpack(f"<{n}I", data[: n * 4]))
    return struct.pack(f"<{n}I", *xxtea_decrypt_words(v))
