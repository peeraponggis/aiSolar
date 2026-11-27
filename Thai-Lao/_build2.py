import csv, json, re, sys, collections, importlib.util
sys.path.insert(0, ".")
spec = importlib.util.spec_from_file_location("translit", "_translit_core.py")
tr = importlib.util.module_from_spec(spec); spec.loader.exec_module(tr)

def norm(s):
    s = s.strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"^to\s+", "", s)
    return re.sub(r"[\s.;:!?]+$", "", s).strip()

def split_eng(s):
    return [p for p in (norm(x) for x in re.split(r"[,;/]", s)) if p]

lao_rows = list(csv.DictReader(open("lao-eng-dictionary.csv", encoding="utf-8")))
gloss_to_lao = collections.defaultdict(set)
lao_info = {}
for r in lao_rows:
    lao_info[r["LaoWord"]] = r["ID"]
    for g in split_eng(r["English"]):
        gloss_to_lao[g].add(r["LaoWord"])

thai_gloss_to_word = collections.defaultdict(set)
thai_words = {}
with open("_kaikki_thai.jsonl", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        w = d["word"]
        gl = [g for s in d.get("senses", []) for g in (s.get("glosses") or [])[:1]]
        if not gl: continue
        thai_words.setdefault(w, gl[0])
        for g in gl[:3]:
            thai_gloss_to_word[norm(g)].add(w)

out = []
seen = set()
def add(lao, thai, eng, method, conf):
    key = (lao, thai)
    if key in seen or lao not in lao_info: return
    seen.add(key)
    out.append([lao_info[lao], lao, thai, tr.lao2thai_script(lao), eng, method, conf])

for g, laos in gloss_to_lao.items():
    thais = thai_gloss_to_word.get(g)
    if not thais or len(laos) > 5 or len(thais) > 5: continue
    for lao in laos:
        for th in thais:
            naive = tr.lao2thai_script(lao)
            conf = "high" if naive == th else "medium"
            add(lao, th, g, "english-pivot", conf)

thai_set = set(thai_words)
for r in lao_rows:
    naive = tr.lao2thai_script(r["LaoWord"])
    if naive in thai_set and len(naive) > 1:
        add(r["LaoWord"], naive, r["English"], "script-cognate", "low")

with open("1_thai-lao.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ID", "LaoWord", "Thai", "Thai_script_naive", "English_gloss", "Method", "Confidence"])
    w.writerows(out)

print("thai-lao rows", len(out), collections.Counter(o[6] for o in out), collections.Counter(o[5] for o in out))
