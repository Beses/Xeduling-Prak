import json
import re
import statistics
from collections import Counter, defaultdict

PATH = "../Datenexport_Praktikum_anonymised.json"
OUT = "json_profile.txt"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def is_num_str(s):
    if not isinstance(s, str) or s.strip() == "": return False
    try:
        float(s.replace(",", "."))
        return True
    except:
        return False


class FS:
    def __init__(s):
        s.n = s.missing = s.null = s.empty = 0
        s.types = Counter()
        s.nums = []
        s.strs = Counter()
        s.bools = Counter()
        s.distinct = set()
        s.capped = False
        s.dates = []

    def add(s, present, v):
        if not present: s.missing += 1; return
        s.n += 1
        if v is None: s.null += 1; s.types['null'] += 1; return
        if isinstance(v, bool): s.types['bool'] += 1; s.bools[v] += 1; return
        if isinstance(v, (int, float)): s.types['number'] += 1; s.nums.append(float(v)); return
        if isinstance(v, str):
            s.types['str'] += 1
            if v == "": s.empty += 1
            if DATE_RE.match(v): s.dates.append(v[:19])
            if is_num_str(v): s.nums.append(float(v.replace(",", ".")))
            if len(s.distinct) < 3000:
                s.distinct.add(v)
            else:
                s.capped = True
            if len(s.strs) < 3000: s.strs[v] += 1
            return
        if isinstance(v, dict): s.types['dict'] += 1; return
        if isinstance(v, list): s.types['list'] += 1; return
        s.types[type(v).__name__] += 1


def profile(records, exclude=()):
    keys = set()
    for r in records:
        if isinstance(r, dict):
            keys |= {k for k in r if k not in exclude and k != "$id"}
    fields = defaultdict(FS)
    total = len(records)
    for r in records:
        if not isinstance(r, dict): continue
        for k in keys:
            p = k in r
            fields[k].add(p, r.get(k) if p else None)
    return fields, total


def fmt(name, f, total):
    cov = 100.0 * f.n / total if total else 0
    out = [f"  - {name}: da {f.n}/{total} ({cov:.0f}%) | null={f.null} leer={f.empty} | typen={dict(f.types)}"]
    if f.nums:
        sv = sorted(f.nums)
        p90 = sv[int(0.9 * (len(sv) - 1))]
        out.append(
            f"      ZAHL: min={min(sv):g} max={max(sv):g} mean={statistics.fmean(sv):.2f} median={statistics.median(sv):g} p90={p90:g} (n={len(sv)})")
    if f.dates:
        out.append(f"      DATUM: {min(f.dates)}  ->  {max(f.dates)}")
    if f.bools:
        out.append(f"      BOOL: {dict(f.bools)}")
    if f.strs:
        if f.capped:
            card = f">{len(f.distinct)}"
            out.append(f"      TEXT: {card} verschiedene Werte")
        else:
            card = str(len(f.distinct))
            out.append(f"      TEXT: ~{card} verschiedene Werte")

        out.append(f"      Häufigste:")
        for val, cnt in f.strs.most_common(10):
            out.append(f"        {cnt:>6}x  {val!r}")
        if len(f.distinct) <= 2 and not f.capped:
            out.append(f"      Alle Werte:")
            for v in sorted(f.distinct):
                out.append(f"        - {v!r}")
    return "\n".join(out)


print("lade JSON (~30s)...", flush=True)
d = json.load(open(PATH))
arts = d.get("$values") or []

artikel = arts
stamm = []
pb = []
zeit = []
asr = []
tools = []
for a in arts:
    if not isinstance(a, dict): continue
    st = a.get("ArbeitsschritteStamm") or {}
    stamm += (st.get("$values") or [])
    for p in (a.get("PBModels") or {}).get("$values") or []:
        pb.append(p)
        zeit += (p.get("Zeiten") or {}).get("$values") or []
        for s in (p.get("Arbeitsschritte") or {}).get("$values") or []:
            asr.append(s)
            tl = s.get("Tools") or {}
            tools += (tl.get("$values") or [])

levels = [
    ("ARTIKEL", artikel, ("PBModels", "ArbeitsschritteStamm")),
    ("ARBEITSSCHRITTE_STAMM (im Artikel)", stamm, ()),
    ("PRODUKTIONSAUFTRAG (PBModel)", pb, ("Zeiten", "Arbeitsschritte")),
    ("ZEIT-BUCHUNG = IST (Zeiten)", zeit, ()),
    ("ARBEITSSCHRITT = PLAN (Arbeitsschritte)", asr, ("Tools",)),
    ("TOOL / Werkzeug", tools, ()),
]
rep = [
    f"Artikel={len(artikel)} Auftraege={len(pb)} Zeiten={len(zeit)} Arbeitsschritte={len(asr)} Tools={len(tools)} Stamm={len(stamm)}",
    "Hierarchie: Artikel -> PBModels(Auftraege) -> {Zeiten=IST, Arbeitsschritte=PLAN -> Tools}"]
for title, recs, excl in levels:
    rep.append("\n" + "=" * 72 + f"\n{title}  (n={len(recs)})\n" + "=" * 72)
    if not recs: rep.append("  (leer)"); continue
    fields, total = profile(recs, excl)
    for k in sorted(fields): rep.append(fmt(k, fields[k], total))
text = "\n\n".join(rep)
open(OUT, "w", encoding="utf-8-sig").write(text)
print(text)
print(f"\n>>> Voller Report auch in Datei: {OUT}")
