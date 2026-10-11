"""Minimal CRI USM demuxer + MP4 conversion via ffmpeg.

Usage: python tools/usm.py <in.usm> [out.mp4]
Chunk layout: sig[4] size(u32be) unk(u8) hdr_off(u8) pad(u16be) chno(u8) .. type(u8 @0x0F); payload at 8+hdr_off.
type 0 = stream data. @SFV = video elementary stream, @SFA = audio (ADX/HCA).
"""
import os
import struct
import subprocess
import sys
import tempfile


def demux(path):
    data = open(path, "rb").read()
    streams = {}
    i = 0
    while i + 0x20 <= len(data):
        sig = data[i:i + 4]
        size = struct.unpack(">I", data[i + 4:i + 8])[0]
        off = data[i + 9]
        pad = struct.unpack(">H", data[i + 10:i + 12])[0]
        chno = data[i + 12]
        typ = data[i + 15] & 3
        if sig in (b"@SFV", b"@SFA", b"@ALP") and typ == 0:
            payload = data[i + 8 + off: i + 8 + size - pad]
            streams.setdefault((sig.decode(), chno), bytearray()).extend(payload)
        i += 8 + size
    return streams


def convert(src, dst, fps=29.97):
    streams = demux(src)
    with tempfile.TemporaryDirectory() as td:
        inputs = []
        for (sig, ch), buf in sorted(streams.items()):
            if sig == "@SFV" and ch == 0:
                p = os.path.join(td, "v.bin")
            elif sig == "@SFA" and ch == 0:
                p = os.path.join(td, "a.bin")
            else:
                continue
            open(p, "wb").write(buf)
            inputs.append(p)
        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        for p in inputs:
            if p.endswith("v.bin"):
                cmd += ["-f", "h264", "-framerate", str(fps), "-i", p]
            else:  # CRI audio: ADX starts with 0x8000, HCA with "HCA\0" (high bits may be masked)
                head = open(p, "rb").read(4)
                fmt = "adx" if head[:2] == b"\x80\x00" else "hca"
                cmd += ["-f", fmt, "-i", p]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart", dst]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    src = sys.argv[1]
    if len(sys.argv) > 2:
        convert(src, sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 29.97)
    else:
        for (sig, ch), buf in demux(src).items():
            print(sig, ch, len(buf), bytes(buf[:16]).hex())
