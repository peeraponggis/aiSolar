# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""Turn a pasted script into clean, Thai-only narration split into scenes.

Thai text is never rewritten by the LLM: it only translates English
sentences and guesses readings for unknown words. Paragraphing, numbers,
acronyms and dictionary readings are done by code, which is exact.
"""
import json
import re

import httpx

from scripts.generate_audio import apply_replacements, load_replacements
from scripts.generate_script import ollama_generate

_DIGITS = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]
_PLACES = ["", "สิบ", "ร้อย", "พัน", "หมื่น", "แสน"]
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", [
    "เอ", "บี", "ซี", "ดี", "อี", "เอฟ", "จี", "เอช", "ไอ", "เจ", "เค", "แอล", "เอ็ม",
    "เอ็น", "โอ", "พี", "คิว", "อาร์", "เอส", "ที", "ยู", "วี", "ดับเบิลยู", "เอ็กซ์", "วาย", "แซด"]))
_ENGLISH = re.compile(r"[A-Za-z](?:[A-Za-z0-9'’.\-]*[A-Za-z0-9])?")
_ENGLISH_RUN = re.compile(r"[A-Za-z][\w'’\-]*(?:[ ,]+[A-Za-z][\w'’\-]*){2,}[.!?]?")
_NUMBER = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(\s*%)?")
_CONNECTORS = ("โดย", "และ", "ซึ่ง", "แต่", "หรือ", "เพราะ", "ทั้งนี้", "นอกจากนี้", "ขณะที่",
               "ส่วน", "จึง", "ดังนั้น", "อย่างไรก็ตาม", "ทำให้", "เนื่องจาก", "สำหรับ", "ด้วย")


# ── Numbers ──

def _below_million(n: int, has_higher: bool) -> str:
    s, out = str(n), []
    for i, ch in enumerate(s):
        d, pos = int(ch), len(s) - i - 1
        if d == 0:
            continue
        if pos == 1:
            out.append("สิบ" if d == 1 else "ยี่สิบ" if d == 2 else _DIGITS[d] + "สิบ")
        elif pos == 0 and d == 1 and (n > 9 or has_higher):
            out.append("เอ็ด")
        else:
            out.append(_DIGITS[d] + _PLACES[pos])
    return "".join(out)


def thai_integer(n: int) -> str:
    if n == 0:
        return "ศูนย์"
    high, low = divmod(n, 1_000_000)
    words = thai_integer(high) + "ล้าน" if high else ""
    return words + (_below_million(low, bool(high)) if low else "")


def numbers_to_thai(text: str) -> str:
    """2569 → สองพันห้าร้อยหกสิบเก้า, 1.7 → หนึ่งจุดเจ็ด, 37% → สามสิบเจ็ด เปอร์เซ็นต์, 45-60 → สี่สิบห้า ถึง หกสิบ"""
    text = re.sub(r"(\d)\s*[-–]\s*(\d)", r"\1 ถึง \2", text)

    def repl(m: re.Match) -> str:
        words = thai_integer(int(m.group(1).replace(",", "")))
        if m.group(2):
            words += "จุด" + "".join(_DIGITS[int(d)] for d in m.group(2))
        if m.group(3):
            words += " เปอร์เซ็นต์"
        return f" {words} "
    return _NUMBER.sub(repl, text)


# ── Scenes ──

def _split_once(p: str) -> list[str] | None:
    """Split a paragraph in two at the best space near its middle."""
    spaces = [m.start() for m in re.finditer(" ", p)]
    if not spaces:
        return None
    mid = len(p) / 2

    def cost(pos: int) -> float:
        before, after = p[:pos], p[pos + 1:]
        c = abs(pos - mid) / len(p)
        if re.search(r"\d\S*$", before) or re.match(r"\d", after):
            c += 1  # keep a number together with its unit
        if before.endswith((".", "!", "?", "ๆ")):
            c -= 0.3
        if after.startswith(_CONNECTORS):
            c -= 0.25
        return c
    pos = min(spaces, key=cost)
    return [p[:pos].strip(), p[pos + 1:].strip()]


def split_scenes(text: str, n: int) -> list[str]:
    """Keep the writer's paragraphs; split the longest / merge the shortest
    neighbours until there are n scenes."""
    paras = [re.sub(r"\s*\n\s*", " ", p).strip() for p in re.split(r"\n\s*\n", text)]
    paras = [p for p in paras if p]
    while 0 < len(paras) < n:
        i = max(range(len(paras)), key=lambda k: len(paras[k]))
        parts = _split_once(paras[i])
        if not parts or min(len(x) for x in parts) < 20:
            break
        paras[i:i + 1] = parts
    while len(paras) > n:
        i = min(range(len(paras) - 1), key=lambda k: len(paras[k]) + len(paras[k + 1]))
        paras[i:i + 2] = [paras[i] + " " + paras[i + 1]]
    return paras


# ── English ──

def spell_acronym(word: str) -> str:
    return " ".join(_LETTERS[c] if c in _LETTERS else _DIGITS[int(c)] if c.isdigit() else ""
                    for c in word.upper()).strip()


def _is_acronym(word: str) -> bool:
    return len(word) <= 8 and word.isupper() and word.isalnum()


async def _ask_json(prompt: str) -> dict:
    try:
        data = json.loads(await ollama_generate(prompt, json_output=True))
    except (ValueError, httpx.HTTPError):
        return {}
    return data if isinstance(data, dict) else {}


async def _translate_sentences(sentences: list[str]) -> dict[str, str]:
    numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
    data = await _ask_json(
        "แปลประโยคภาษาอังกฤษต่อไปนี้เป็นภาษาไทยที่เป็นธรรมชาติ สำหรับผู้ประกาศข่าวอ่าน "
        "คงชื่อบริษัท ชื่อคน และตัวย่อเป็นภาษาอังกฤษตามเดิม ห้ามสรุปหรือเพิ่มเนื้อหา "
        'ตอบเป็น JSON object รูปแบบ {"1": "คำแปล", "2": "คำแปล"} เท่านั้น\n' + numbered)
    out = {}
    for i, s in enumerate(sentences):
        t = data.get(str(i + 1))
        if isinstance(t, str) and re.search(r"[฀-๿]", t):
            out[s] = t.strip()
    return out


async def _guess_readings(words: list[str]) -> dict[str, str]:
    data = await _ask_json(
        "ให้คำอ่านภาษาไทยของชื่อหรือคำภาษาอังกฤษต่อไปนี้ ตามที่คนไทยออกเสียง "
        'ตอบเป็น JSON object รูปแบบ {"คำอังกฤษ": "คำอ่านไทย"} เท่านั้น\n' + "\n".join(words))
    return {k: v.strip() for k, v in data.items()
            if k in words and isinstance(v, str) and re.search(r"[฀-๿]", v)
            and not re.search(r"[A-Za-z]", v)}


def _tidy(text: str) -> str:
    # Dictionary readings use hyphens between syllables; spaces read better on screen.
    text = re.sub(r"(?<=[฀-๿])-+|-+(?=[฀-๿])", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.!?)])", r"\1", text)
    return text.strip()


def normalize_for_speech(text: str, dictionary: dict | None = None) -> str:
    """Code-only pass (no LLM): numbers to Thai words, dictionary readings,
    upper-case acronyms spelled out. Keeps the line structure (A:/B: lines)."""
    dictionary = load_replacements() if dictionary is None else dictionary
    out = []
    for line in text.translate(_THAI_DIGITS).split("\n"):
        speaker = re.match(r"^\s*([AB]\s*[:：]\s*)", line)
        prefix = speaker.group(1) if speaker else ""
        body = line[len(prefix):]
        # A list marker ("1. ตื่นนอน...") is read "ข้อที่หนึ่ง", not "หนึ่ง จุด".
        body = re.sub(r"(^|\s)(\d{1,2})\.(?=\s)", r"\1ข้อที่ \2", body)
        body = apply_replacements(numbers_to_thai(body), dictionary)
        acronyms = {w: spell_acronym(w) for w in _ENGLISH.findall(body) if _is_acronym(w)}
        body = apply_replacements(body, acronyms)
        out.append(prefix + _tidy(body))
    return "\n".join(out)


def leftover_english(text: str) -> list[str]:
    return sorted(set(_ENGLISH.findall(re.sub(r"^\s*[AB]\s*[:：]", "", text, flags=re.M))))


async def normalize_script(text: str, scenes: int) -> dict:
    warnings = []
    text = text.translate(_THAI_DIGITS).replace("\r", "")

    runs = sorted(set(m.group(0).strip() for m in _ENGLISH_RUN.finditer(text)))
    if runs:
        try:
            translated = await _translate_sentences(runs)
        except httpx.HTTPError:
            translated = {}
            warnings.append("เชื่อมต่อ Ollama ไม่ได้ — ประโยคภาษาอังกฤษยังไม่ได้แปล")
        for src in sorted(translated, key=len, reverse=True):
            text = text.replace(src, translated[src])

    paras = split_scenes(text, scenes)
    dictionary = load_replacements()
    paras = [apply_replacements(numbers_to_thai(p), dictionary) for p in paras]

    acronyms = {w: spell_acronym(w) for p in paras for w in _ENGLISH.findall(p) if _is_acronym(w)}
    paras = [apply_replacements(p, acronyms) for p in paras]

    unknown = sorted({w for p in paras for w in _ENGLISH.findall(p)})
    guessed = {}
    if unknown:
        try:
            guessed = await _guess_readings(unknown)
        except httpx.HTTPError:
            guessed = {}
        paras = [apply_replacements(p, guessed) for p in paras]
        left = sorted({w for p in paras for w in _ENGLISH.findall(p)})
        if left:
            warnings.append("ยังมีคำอังกฤษที่ไม่มีคำอ่าน: " + ", ".join(left[:10]))

    paras = [_tidy(p) for p in paras if p.strip()]
    return {"text": "\n\n".join(paras), "paragraphs": len(paras),
            "guessed": {**acronyms, **guessed}, "warnings": warnings}
