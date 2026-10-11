"""Map NovelCommand classes -> vtable -> construction sites in libapp.so."""
import re, sys, json, collections
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from elfre import Bin, LIB
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

b = Bin()
elf = ELFFile(open(LIB, 'rb'))
rel = {}  # addend -> [offsets]
for sec in elf.iter_sections():
    if isinstance(sec, RelocationSection) and sec.name == '.rela.dyn':
        for r in sec.iter_relocations():
            rel.setdefault(r.entry['r_addend'], []).append(r['r_offset'])

names = sorted(set(m.group(0).decode() for m in re.finditer(rb'N6toybox(?:3gui)?\d+NovelCommand[A-Za-z]+E\x00', b.data)))
out = {}
for n in names:
    n = n.rstrip('\x00')
    sva = b.find_str(n.encode() + b'\0')[0]
    tis = [o - 8 for o in rel.get(sva, [])]           # typeinfo: [vptr, name*, base*]
    vts = [o - 8 for t in tis for o in rel.get(t, [])]  # vtable: [off2top, typeinfo*, fn...]
    sites = sorted(set(x for v in vts for x in b.xrefs(v + 16)))
    out[re.sub(r'^N6toybox(3gui)?\d+|E$', '', n)] = [hex(s) for s in sites]
json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else 'vt_sites.json', 'w'), indent=1)  # optional output path
for k, v in out.items():
    print(k, v[:4])
