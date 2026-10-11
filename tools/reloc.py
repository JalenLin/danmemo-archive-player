import sys
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

LIB = config.load()["libapp"]  # your own libapp.so, from config.json
targets = {int(x, 16) for x in sys.argv[1:]}
elf = ELFFile(open(LIB, "rb"))
for sec in elf.iter_sections():
    if isinstance(sec, RelocationSection):
        for r in sec.iter_relocations():
            a = r.entry.get("r_addend", 0)
            if a in targets:
                print(sec.name, hex(r["r_offset"]), hex(a))
