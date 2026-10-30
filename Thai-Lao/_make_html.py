# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

import csv, json, importlib.util
lao = [[r["ID"], r["LaoWord"], r["English"], r["Pronunciation"], r["Type"]]
       for r in csv.DictReader(open("lao-eng-dictionary.csv", encoding="utf-8"))]
th = [[r["ID"], r["LaoWord"], r["Thai"], r["English_gloss"], r["Method"], r["Confidence"]]
      for r in csv.DictReader(open("1_thai-lao.csv", encoding="utf-8"))]
spec = importlib.util.spec_from_file_location("translit", "_translit_core.py")
tr = importlib.util.module_from_spec(spec); spec.loader.exec_module(tr)
mapping = {k: v for k, v in tr.lao2thai_transliteration.items()}
data = json.dumps({"lao": lao, "th": th}, ensure_ascii=False, separators=(",", ":")).replace("</", "<\/")
mp = json.dumps(mapping, ensure_ascii=False, separators=(",", ":"))
html = open("_template.html", encoding="utf-8").read().replace("__DATA__", data).replace("__MAP__", mp)
open("dictionary.html", "w", encoding="utf-8").write(html)
print("bytes", len(html.encode("utf-8")), "map entries", len(mapping))
