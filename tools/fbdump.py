"""Heuristic schemaless FlatBuffers dumper for DanMemo data (strings are XXTEA-encrypted)."""
import struct
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import dmcrypto as D


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def i32(b, o):
    return struct.unpack_from("<i", b, o)[0]


def try_string(b, o):
    """o = position of the uoffset field; returns decrypted str or None."""
    if o + 4 > len(b):
        return None
    t = o + u32(b, o)
    if t + 4 > len(b):
        return None
    L = u32(b, t)
    if L == 0:
        return ""
    if L % 4 or L < 8 or t + 4 + L > len(b):
        return None
    r = D.xxtea_decrypt(b[t + 4 : t + 4 + L])
    n = u32(r, len(r) - 4)
    if not (len(r) - 7 <= n <= len(r) - 4):
        return None
    s = r[:n]
    if s.endswith(b"\0"):
        s = s[:-1]
    try:
        return s.decode("utf-8")
    except UnicodeDecodeError:
        return None


def table_fields(b, t):
    vt = t - i32(b, t)
    if not (0 <= vt < len(b) - 4):
        return None
    vlen, tlen = struct.unpack_from("<HH", b, vt)
    if vlen < 4 or vlen % 2 or vt + vlen > len(b):
        return None
    n = (vlen - 4) // 2
    offs = struct.unpack_from(f"<{n}H", b, vt + 4)
    return tlen, offs


def looks_table(b, t):
    if t < 0 or t + 4 > len(b) or t % 4 or (t - i32(b, t)) % 2:
        return False
    r = table_fields(b, t)
    if not r:
        return False
    tlen, offs = r
    return all(o < tlen for o in offs) and tlen < 4096


def field_sizes(offs, tlen):
    present = sorted(o for o in offs if o)
    sizes = {}
    for i, o in enumerate(present):
        nxt = present[i + 1] if i + 1 < len(present) else tlen
        sizes[o] = nxt - o
    return sizes


def enc_scalar(b, p, maxlen):
    """Inline scalars are XXTEA blocks whose last plaintext word is the payload length:
    8 bytes = (int32 | byte, len 4 | 1), 12 bytes = (int64 lo, hi, len 8). Returns the value or None."""
    for n in (8, 12):
        if n > maxlen or p + n > len(b):
            return None
        w = struct.unpack(f"<{n // 4}I", D.xxtea_decrypt(b[p : p + n]))
        dl = w[-1]
        if n == 8 and dl == 4:
            return struct.unpack("<i", struct.pack("<I", w[0]))[0]
        if n == 8 and dl == 1:
            return w[0] & 0xFF
        if n == 12 and dl == 8:
            return struct.unpack("<q", struct.pack("<II", w[0], w[1]))[0]
    return None


def is64_here(b, t, tlen, offs, fo):
    """int64 candidate: >= 8 bytes before next field and 8-aligned relative to buffer end."""
    p = t + fo
    return field_sizes(offs, tlen)[fo] >= 8 and (len(b) - p) % 8 == 0


def dump(b, t, depth=0, maxdepth=8, col64=None):
    """col64: optional {field_idx: bool} decided across all rows of the parent vector."""
    tlen, offs = table_fields(b, t)
    sizes = field_sizes(offs, tlen)
    res = {}
    for idx, fo in enumerate(offs):
        if not fo:
            continue
        p = t + fo
        sz = sizes[fo]
        val = enc_scalar(b, p, sz)
        if val is not None:
            res[idx] = val
            continue
        if sz >= 4 and fo % 4 == 0:
            s = try_string(b, p)
            if s is not None:
                val = s
            else:
                tgt = p + u32(b, p)
                if depth < maxdepth and tgt + 4 <= len(b):
                    val = try_vector(b, tgt, depth)
                if val is None and depth < maxdepth and tgt < len(b) and looks_table(b, tgt):
                    val = dump(b, tgt, depth + 1)
        if val is None:
            wide = col64.get(idx, False) if col64 is not None else is64_here(b, t, tlen, offs, fo)
            if wide:
                val = struct.unpack_from("<q", b, p)[0]
                # 8-byte inline field = XXTEA-encrypted int32 scalar (value word + length word 4)
                dv, dl = struct.unpack("<iI", D.xxtea_decrypt(b[p : p + 8]))
                if dl == 4:  # encrypted int32
                    val = dv
                elif dl == 1:  # encrypted bool / byte
                    val = dv & 0xFF
            elif sz >= 4:
                val = i32(b, p)
            elif sz >= 2:
                val = struct.unpack_from("<h", b, p)[0]
            else:
                val = b[p]
        res[idx] = val
    return res


def try_vector(b, v, depth):
    n = u32(b, v)
    if n == 0 or n > 2000000 or v + 4 + 4 * n > len(b):
        return None
    elems = []
    for i in range(n):
        p = v + 4 + 4 * i
        s = try_string(b, p)
        if s is not None:
            elems.append(s)
            continue
        tgt = p + u32(b, p)
        if tgt < len(b) and looks_table(b, tgt):
            elems.append(tgt)
        else:
            return None
    # decide int64 vs int32 per column across all rows
    col64 = {}
    for t in elems:
        if isinstance(t, str):
            continue
        tlen, offs = table_fields(b, t)
        for idx, fo in enumerate(offs):
            if fo:
                col64[idx] = col64.get(idx, True) and is64_here(b, t, tlen, offs, fo)
    return [e if isinstance(e, str) else dump(b, e, depth + 1, col64=col64) for e in elems]


def load(path):
    out = D.decrypt_file(open(path, "rb").read())
    return out, dump(out, u32(out, 0))


if __name__ == "__main__":
    import json
    for path in sys.argv[1:]:
        _, d = load(path)
        print(json.dumps(d, ensure_ascii=False, indent=1))
