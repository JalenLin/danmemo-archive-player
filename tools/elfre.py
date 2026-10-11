"""Small aarch64 ELF helper: string lookup, ADRP/ADD xrefs, BL callers, disassembly."""
import sys
import numpy as np
from elftools.elf.elffile import ELFFile
import capstone

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

LIB = config.load()["libapp"]  # your own libapp.so, from config.json


class Bin:
    def __init__(self, path=LIB):
        self.data = open(path, "rb").read()
        elf = ELFFile(open(path, "rb"))
        self.segs = []
        for s in elf.iter_segments():
            if s["p_type"] == "PT_LOAD":
                self.segs.append((s["p_vaddr"], s["p_offset"], s["p_filesz"], s["p_memsz"]))
        text = elf.get_section_by_name(".text")
        self.text_addr = text["sh_addr"]
        self.text_off = text["sh_offset"]
        self.text_size = text["sh_size"]
        self.words = np.frombuffer(self.data, dtype="<u4", count=self.text_size // 4, offset=self.text_off)
        self.md = capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM)
        self.syms = {}
        dyn = elf.get_section_by_name(".dynsym")
        for sym in dyn.iter_symbols():
            if sym["st_value"]:
                self.syms[sym["st_value"]] = sym.name

    def off2va(self, off):
        for va, fo, fs, ms in self.segs:
            if fo <= off < fo + fs:
                return va + off - fo

    def va2off(self, va):
        for v, fo, fs, ms in self.segs:
            if v <= va < v + fs:
                return fo + va - v

    def find_str(self, s):
        b = s.encode() if isinstance(s, str) else s
        res, i = [], 0
        while True:
            i = self.data.find(b, i)
            if i < 0:
                return res
            res.append(self.off2va(i))
            i += 1

    def cstr(self, va, maxlen=256):
        o = self.va2off(va)
        if o is None:
            return None
        e = self.data.find(b"\0", o, o + maxlen)
        return self.data[o:e if e >= 0 else o + maxlen]

    def xrefs(self, target):
        """ADRP+ADD (or ADRP+LDR) pairs resolving to target. Returns instruction VAs of ADRP."""
        w = self.words
        adrp = (w & 0x9F000000) == 0x90000000
        idx = np.nonzero(adrp)[0]
        ww = w[idx].astype(np.int64)
        immlo = (ww >> 29) & 3
        immhi = (ww >> 5) & 0x7FFFF
        imm = (immhi << 2) | immlo
        imm = np.where(imm & (1 << 20), imm - (1 << 21), imm)
        pc = self.text_addr + idx.astype(np.int64) * 4
        page = (pc & ~0xFFF) + (imm << 12)
        cand = idx[page == (target & ~0xFFF)]
        out = []
        for i in cand:
            rd = int(w[i]) & 31
            for j in range(i + 1, min(i + 8, len(w))):
                ins = int(w[j])
                # ADD Xd, Xn, #imm
                if (ins & 0xFF800000) == 0x91000000 and ((ins >> 5) & 31) == rd:
                    sh = (ins >> 22) & 1
                    im = ((ins >> 10) & 0xFFF) << (12 * sh)
                    if (target & ~0xFFF) + im == target:
                        out.append(self.text_addr + i * 4)
                    break
                # LDR Xt, [Xn, #imm]
                if (ins & 0xFFC00000) == 0xF9400000 and ((ins >> 5) & 31) == rd:
                    im = ((ins >> 10) & 0xFFF) * 8
                    if (target & ~0xFFF) + im == target:
                        out.append(self.text_addr + i * 4)
                    break
        return out

    def callers(self, target):
        w = self.words
        bl = (w & 0xFC000000) == 0x94000000
        idx = np.nonzero(bl)[0]
        imm = (w[idx].astype(np.int64) & 0x3FFFFFF)
        imm = np.where(imm & (1 << 25), imm - (1 << 26), imm)
        pc = self.text_addr + idx.astype(np.int64) * 4
        return [int(x) for x in pc[pc + imm * 4 == target]]

    def func_start(self, va, maxback=0x4000):
        """Heuristic: walk back to the previous RET / unconditional branch boundary followed by prologue."""
        i = (va - self.text_addr) // 4
        for k in range(i, max(0, i - maxback // 4), -1):
            prev = int(self.words[k - 1])
            if prev == 0xD65F03C0 or (prev & 0xFC000000) == 0x14000000 or prev == 0:
                cur = int(self.words[k])
                # sub sp / stp ... pre-index / paciasp etc
                if (cur & 0xFF0003FF) == 0xD10003FF or (cur & 0xFFC003E0) == 0xA98003E0 or cur == 0xD503233F \
                        or (cur & 0xFFC003E0) == 0xA9800000 | (31 << 5) or (cur & 0xFFE0FFFF) == 0xF81F0FFE:
                    return self.text_addr + k * 4
        return None

    def dis(self, va, n=60):
        o = self.va2off(va)
        out = []
        for ins in self.md.disasm(self.data[o:o + n * 4], va):
            note = ""
            if ins.mnemonic == "bl":
                t = int(ins.op_str.lstrip("#"), 16)
                note = self.syms.get(t, "")
            out.append(f"{ins.address:#x}: {ins.mnemonic:8s} {ins.op_str} {note}")
        return "\n".join(out)
