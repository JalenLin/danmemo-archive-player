"""Card stat calculator (reverse-engineered against the memorial app's キャラ詳細 screen)."""
import collections, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
DEC = config.load()["dec"]
L = lambda t: json.load(open(f"{DEC}/master/{t}.json", encoding="utf-8"))["0"]
STATS = [(2, "力"), (16, "耐久"), (32, "器用"), (8, "敏捷"), (4, "魔力")]
_ab = {r["0"]: r for r in L("pcAbility")}
_job = {r["0"]: r for r in L("pcJob")}
_pan = collections.defaultdict(list)
for r in L("pcAbilityPanel"):
    _pan[r.get("1", 0)].append(r)
for v in _pan.values():
    v.sort(key=lambda r: r.get("2", 0))
PC = {r["0"]: r for r in L("pc")}

def panel_sum(rows):
    t = collections.Counter()
    for p in rows:
        a = _ab.get(p.get("3"), {})
        if a.get("1") == 50:
            for b, n in STATS:
                if a.get("7", 0) & b:
                    t[n] += a.get("6", 0)
    return t

def pct(c):
    t = collections.Counter()
    for f in range(30, 40, 2):
        a = _ab.get(c.get(str(f)), {})
        if a.get("5") == 16:
            for b, n in STATS:
                if a.get("7", 0) & b:
                    t[n] += a.get("6", 0)
    return t

def stats(cid, lb, base_fields):
    c = PC[cid]
    board = collections.Counter()
    for f in ("14", "15", "16", "17", "18", "19"):
        j = _job.get(c.get(f))
        if j:
            board += panel_sum(_pan[j.get("11")])
    lbj = _job.get(c.get("20"))
    lbs = panel_sum(_pan[lbj.get("11")][: lb * 5]) if lbj and lb else collections.Counter()
    p = pct(c)
    out = {}
    for (b, n), f in zip(STATS, base_fields):
        pre = c.get(str(f), 0) + board[n] + lbs[n]
        out[n] = (pre + math.floor(pre * p[n] / 10000), math.floor(pre * p[n] / 10000))
    return out
