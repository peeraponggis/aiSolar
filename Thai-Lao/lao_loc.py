# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

# Lao -> LOC 2012 romanization, rule-based, following the Lao Romanization Table (2012).
# romanize() raises Unsupported for constructions outside the table.

CONS_INI = {
    "ກ": "k", "ຂ": "kh", "ຄ": "kh", "ງ": "ng", "ຈ": "ch", "ສ": "s", "ຊ": "s",
    "ຍ": "ny", "ດ": "d", "ຕ": "t", "ຖ": "th", "ທ": "th", "ນ": "n", "ບ": "b",
    "ປ": "p", "ຜ": "ph", "ຝ": "f", "ພ": "ph", "ຟ": "f", "ມ": "m", "ຢ": "y",
    "ຣ": "r", "ລ": "l", "ວ": "v", "ຫ": "h", "ອ": "ʻ", "ຮ": "h",
    "ໜ": "n", "ໝ": "m",
}
CONS_FIN = {
    "ກ": "k", "ຂ": "k", "ຄ": "k", "ງ": "ng", "ຈ": "t", "ສ": "t", "ຊ": "t",
    "ດ": "t", "ຕ": "t", "ຖ": "t", "ທ": "t", "ນ": "n", "ບ": "p", "ປ": "p",
    "ຜ": "p", "ຝ": "p", "ພ": "p", "ຟ": "p", "ມ": "m", "ຣ": "n", "ລ": "n",
    "ຢ": "", "ຫ": "", "ອ": "", "ຮ": "", "ວ": "o", "ຍ": "i", "ໜ": "n", "ໝ": "m",
}
LEAD = set("ເແໂໄໃ")
POST = set("ະັາຳິີຶືຸູົໍຽອ")
TONES = set("່້໊໋")
SUB_L = "ຼ"
DIGITS = {c: str(i) for i, c in enumerate("໐໑໒໓໔໕໖໗໘໙")}
CONS = set(CONS_INI)

VOWEL = {
    ("", frozenset()): "o",
    ("", frozenset("ະ")): "a", ("", frozenset("ັ")): "a", ("", frozenset("າ")): "ā",
    ("", frozenset("ິ")): "i", ("", frozenset("ີ")): "ī", ("", frozenset("ຶ")): "ư",
    ("", frozenset("ື")): "ư̄", ("", frozenset("ຸ")): "u", ("", frozenset("ູ")): "ū",
    ("", frozenset("ຽ")): "ia", ("", frozenset("ົ")): "ǭ", ("", frozenset("ໍ")): "ǭ",
    ("", frozenset("ຳ")): "am", ("", frozenset("ອ")): "o",
    ("ເ", frozenset("ະ")): "e", ("ເ", frozenset("ັ")): "e", ("ເ", frozenset()): "ē",
    ("ແ", frozenset("ະ")): "æ", ("ແ", frozenset("ັ")): "æ", ("ແ", frozenset()): "ǣ",
    ("ໂ", frozenset("ະ")): "o", ("ໂ", frozenset()): "ō",
    ("ເ", frozenset("າ")): "ǫ", ("ເ", frozenset("ົາ")): "āo",
    ("ເ", frozenset("ີະ")): "œ", ("ເ", frozenset("ີ")): "œ̄",
    ("ເ", frozenset("ຍ")): "ia", ("ເ", frozenset("ຽ")): "ia",
    ("ໄ", frozenset()): "ai", ("ໃ", frozenset()): "ai",
    ("ເ", frozenset("ັວ")): "ưa", ("ເ", frozenset("ົວ")): "ư̄a",
}


class Unsupported(Exception):
    pass


def _flush(s, out):
    if not (s["ini"] or s["lead"] or s["vows"] or s["med"] or s["fin"]):
        return
    ini, lead, med, fin = s["ini"], s["lead"], s["med"], s["fin"]
    vows = frozenset(s["vows"])
    head = ""
    final_override = None
    if ini:
        if ini == "ຫ" and s["hdrop"]:
            head = ""
        elif ini == "ຫ" and med == SUB_L:
            head = "l"
            med = None
        else:
            head = CONS_INI[ini]
    if med == SUB_L:
        med = None
    key = (lead, vows)
    if key not in VOWEL:
        raise Unsupported(f"{lead}{''.join(sorted(vows))}")
    vow = VOWEL[key]
    if fin == "ຍ" and not vows and lead == "ເ":
        vow, fin = "ia", None
    elif fin == "ຍ" and vows:
        pass
    if med == "ວ":
        if fin and not vows and ini in ("ກ", "ຂ", "ຄ"):
            head += "w"
            vow = "ā"
        elif fin == "ງ" and not vows:
            vow, final_override = "ūa", "i"
        elif fin and not vows:
            vow = "ūa"
        elif not fin and vows:
            head += "w"
        elif not vows:
            head += "w"
    if fin is not None and fin not in CONS_FIN:
        raise Unsupported(fin)
    final = "" if fin is None else CONS_FIN[fin]
    if final_override is not None:
        final = final_override
    out.append(head + vow + final)
    s.update(ini=None, lead="", vows=[], med=None, fin=None, hdrop=False)


def romanize(word):
    out = []
    s = {"ini": None, "lead": "", "vows": [], "med": None, "fin": None, "hdrop": False}
    chars = list(word)
    for i, ch in enumerate(chars):
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if ch in TONES or ch == "ໆ":
            continue
        if ch in DIGITS:
            _flush(s, out); out.append(DIGITS[ch]); continue
        if ch.isspace() or ch == "-":
            _flush(s, out); out.append(ch); continue
        if ch in LEAD:
            _flush(s, out)
            s["lead"] = ch
        elif ch in CONS:
            nucleus = bool(s["vows"] or s["lead"] or s["med"])
            if s["fin"]:
                _flush(s, out); s["ini"] = ch
            elif s["ini"] is None:
                s["ini"] = ch
            elif ch in "ໜໝ" and s["ini"] is None:
                s["ini"] = ch
            elif s["ini"] == "ຫ" and ch in "ຍນມຣລວ" and not nucleus:
                s["hdrop"] = True; s["ini"] = ch
            elif ch == "ວ" and not nucleus:
                s["med"] = ch
            elif ch == "ອ" and not nucleus:
                s["vows"].append("ອ")
            elif nucleus:
                if nxt in POST or nxt == SUB_L:
                    _flush(s, out); s["ini"] = ch
                else:
                    s["fin"] = ch
            else:
                _flush(s, out); s["ini"] = ch
        elif ch == SUB_L:
            s["med"] = SUB_L
        elif ch in POST:
            s["vows"].append(ch)
        else:
            raise Unsupported(ch)
    _flush(s, out)
    return "".join(out).strip()
