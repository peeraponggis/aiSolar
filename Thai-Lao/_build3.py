import csv, collections, sys
sys.path.insert(0, ".")
from lao_loc import romanize, Unsupported

rows = list(csv.DictReader(open("lao-eng-dictionary.csv", encoding="utf-8")))
freelang = {r["ID"]: r["Romanization"] for r in csv.DictReader(open("3_romanization.csv", encoding="utf-8"))}
thai = collections.defaultdict(list)
for r in csv.DictReader(open("1_thai-lao.csv", encoding="utf-8")):
    if r["Confidence"] in ("high", "medium"):
        thai[r["LaoWord"]].append(r["Thai"])

stats = collections.Counter()
out = []
for r in rows:
    try:
        loc = romanize(r["LaoWord"]); src = "LOC-2012"; stats["loc"] += 1
    except Unsupported:
        loc = ""; stats["fallback"] += 1
        src = "fallback-English" if r["English"] else "fallback-none"
    th = "; ".join(dict.fromkeys(thai.get(r["LaoWord"], [])))
    if not loc:
        stats["thai_fallback_filled"] += bool(th)
    out.append([r["ID"], r["LaoWord"], loc, src, r["English"], th, r["Type"], freelang.get(r["ID"], "")])

with open("4_standard-merged.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ID", "LaoWord", "Romanization_LOC", "Source", "English", "Thai", "Type", "FREELANG_ref"])
    w.writerows(out)
print(dict(stats))
