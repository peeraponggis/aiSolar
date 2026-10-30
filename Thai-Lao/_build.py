import csv, re, collections
SRC = "raw_lao-eng-dictionary.csv"
HDR_WORDS = {"LaoWord", "Lao", ""}

def is_lao(s):
    return any('\u0e80' <= c <= '\u0eff' for c in s)

def norm_type(t):
    t = re.sub(r"\s+", " ", t.strip().lower()).rstrip(":.")
    return {"pre": "prep", "types": "", "type": ""}.get(t, t)

def clean(s):
    return re.sub(r"\s+", " ", s).strip()

stats = collections.Counter()
rows = []
with open(SRC, encoding="utf-8", newline="") as f:
    r = csv.reader(f); next(r)
    for rid, lao, eng, pron, typ in r:
        lao, eng, pron, typ = map(clean, (lao, eng, pron, typ))
        if lao in HDR_WORDS and eng in ("English", "") and pron.lower().startswith("pron"):
            stats["embedded_header_removed"] += 1; continue
        if not lao or not is_lao(lao):
            stats["no_lao_headword_removed"] += 1; continue
        if not eng and not pron:
            stats["no_meaning_no_pron_removed"] += 1; continue
        rows.append([rid, lao, eng, pron, norm_type(typ)])

seen = set(); clean_rows = []
for row in rows:
    key = (row[1], row[2], row[3])
    if key in seen:
        stats["exact_duplicate_removed"] += 1; continue
    seen.add(key); clean_rows.append(row)

def write(path, header, data):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(header); w.writerows(data)

write("lao-eng-dictionary.csv", ["ID", "LaoWord", "English", "Pronunciation", "Type"], clean_rows)
write("2_eng-lao.csv", ["ID", "LaoWord", "English", "Type"],
      [[i, l, e, t] for i, l, e, p, t in clean_rows if e])
write("3_romanization.csv", ["ID", "LaoWord", "Romanization"],
      [[i, l, p] for i, l, e, p, t in clean_rows if p])
write("1_thai-lao.csv", ["ID", "LaoWord", "Thai", "Note"], [])
merged = []
for i, l, e, p, t in clean_rows:
    src = "standard-base" if p else ("english-fallback" if e else "none")
    merged.append([i, l, p, e, "", t, src])
write("4_standard-merged.csv",
      ["ID", "LaoWord", "Romanization", "English", "Thai", "Type", "Source"], merged)

stats["clean_rows"] = len(clean_rows)
stats["romanization_present"] = sum(1 for m in merged if m[6] == "standard-base")
stats["english_fallback"] = sum(1 for m in merged if m[6] == "english-fallback")
stats["no_romanization_no_english"] = sum(1 for m in merged if m[6] == "none")
for k, v in sorted(stats.items()): print(f"{k}: {v}")
