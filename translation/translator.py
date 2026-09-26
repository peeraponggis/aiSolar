#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local Translator - โปรแกรมช่วยแปลบนเดสก์ท็อป ใช้โมเดลในเครื่องผ่าน Ollama
โมเดลหลัก: scb10x/typhoon2.5-qwen3-4b (ไทย-อังกฤษ, รัน 100% บน GPU 4GB)

เปิดด้วยทางลัด "แปลภาษา Local" (เรียก LocalTranslator.exe) หรือรันจากซอร์สโค้ด:
    python translator.py                       เปิดหน้าต่างโปรแกรม (เปิด Ollama ให้เองถ้ายังไม่ทำงาน)
    python translator.py --cli "ข้อความ"        แปลใน console (ทดสอบ)
    python translator.py --cli --level engineering --to en "ข้อความ"

    python translator.py --minimized            เปิดแบบย่อหน้าต่าง (ใช้กับ Startup)

ฟีเจอร์: เลือกระดับการแปล 6 แบบ, ตรวจภาษาต้นทางอัตโนมัติ, สตรีมคำแปล,
ไอคอนลอยเมื่อลากคลุมข้อความในโปรแกรมใดก็ได้ (คลิกแล้วแปลทันที),
คีย์ลัด Ctrl+Alt+T, เฝ้าคลิปบอร์ด, พจนานุกรมศัพท์ glossary.txt, ประวัติ history.json,
เสียงอ่านคำแปล (edge-tts เปรมวดี/นิวัฒน์ + ตารางคำอ่าน + โคลนเสียง จากโปรเจกต์ F:/LocalAI/yt)
"""
import argparse
import ctypes
import json
import math
import os
import queue
import re
import sys
import threading
import time
import urllib.error
import urllib.request

FROZEN = bool(getattr(sys, "frozen", False))          # รันจาก exe ที่สร้างด้วย PyInstaller
BASE = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = "http://" + os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").replace("http://", "")
DEFAULT_MODEL = os.environ.get("TRANSLATOR_MODEL", "scb10x/typhoon2.5-qwen3-4b:latest")
# ลำดับสำรองถ้าโมเดลหลักไม่มี (เรียงตามคุณภาพภาษาไทยและความเร็วบน VRAM 4GB)
FALLBACK_MODELS = ["scb10x/typhoon2.5-qwen3-4b", "qwen2.5:7b-instruct", "qwen2.5:7b",
                   "scb10x/llama3.2-typhoon2-3b-instruct", "llama3.1:8b", "hermes3:3b"]
NUM_CTX = 4096          # 4096 ทำให้รัน 100% GPU บน RTX A500 4GB
KEEP_ALIVE = "30m"
GLOSSARY_FILE = os.path.join(BASE, "glossary.txt")
HISTORY_FILE = os.path.join(BASE, "history.json")
SETTINGS_FILE = os.path.join(BASE, "settings.json")
MAX_HISTORY = 200
HOTKEY_LABEL = "Ctrl+Alt+T"
# ---- เสียงอ่าน: ใช้ของโปรเจกต์ yt (edge-tts + replacements.json + โคลนเสียง OpenVoice)
YT_DIR = os.path.normpath(os.path.join(BASE, "..", "yt"))
REPLACEMENTS_FILE = os.path.join(YT_DIR, "config", "replacements.json")
TTS_TMP = os.path.join(os.environ.get("TEMP", BASE), "thai-translator-tts")
TTS_VOICES = {  # ชื่อที่แสดง -> (ชื่อเสียง edge-tts หรือ sapi:ชื่อเสียง Windows, ภาษา)
    "เปรมวดี (หญิง)": ("th-TH-PremwadeeNeural", "th"),
    "นิวัฒน์ (ชาย)": ("th-TH-NiwatNeural", "th"),
    "ปัตตรา (ในเครื่อง เร็ว ออฟไลน์)": ("sapi:Pattara", "th"),
}
EN_VOICES = {"th-TH-PremwadeeNeural": "en-US-JennyNeural", "th-TH-NiwatNeural": "en-US-GuyNeural", "sapi:Pattara": "sapi:Zira"}
TTS_RATES = {"ช้า": "-20%", "ปกติ": "+0%", "เร็ว": "+20%", "เร็วมาก": "+40%"}

# ---------------------------------------------------------------- ระดับการแปล
LEVELS = {
    "general": {
        "label": "ทั่วไป",
        "desc": "ภาษาธรรมชาติ อ่านลื่น สำหรับบทสนทนา บทความ ข้อความทั่วไป",
        "temp": 0.3,
        "prompt": (
            "Register: everyday, natural language. Translate faithfully but make it read like a native speaker wrote it. "
            "Keep the tone of the original (casual stays casual, polite stays polite). "
            "Thai output: use natural spoken-written Thai with polite particles only where the source implies them."
        ),
    },
    "email": {
        "label": "ส่งอีเมล",
        "desc": "สำนวนจดหมายธุรกิจ สุภาพ เป็นทางการ คงโครงสร้างคำขึ้นต้น-ลงท้าย",
        "temp": 0.25,
        "prompt": (
            "Register: professional business email. Polite, clear, concise, formal but warm. "
            "Preserve the email structure exactly: subject line, greeting, paragraphs, bullet points, sign-off, signature block, "
            "and any placeholders like [Name] or dates. Use standard conventions of the target language "
            "(English: 'Dear ...', 'Best regards'; Thai: 'เรียน ...', 'ขอแสดงความนับถือ', polite particles ครับ/ค่ะ as appropriate). "
            "Do not add content that is not in the source: never invent a subject line, greeting, sign-off, attachment mention or name that the source does not contain."
        ),
    },
    "engineering": {
        "label": "วิศวกรรม",
        "desc": "ศัพท์เทคนิคแม่นยำ คงตัวเลข หน่วย รหัสมาตรฐาน รุ่นอุปกรณ์ (เหมาะกับงานไฟฟ้า/โซลาร์/BOQ)",
        "temp": 0.15,
        "prompt": (
            "Register: technical engineering document (electrical, solar PV, construction, BOQ, specifications, method statements). "
            "Use precise standard engineering terminology. Keep ALL numbers, units, tolerances, part numbers, model names, "
            "standard codes (IEC, IEEE, มอก./TIS, PEA, MEA, EIT) and abbreviations exactly as written. "
            "Do not paraphrase specifications; do not add or remove requirements. Keep tables and lists line-by-line. "
            "Prefer terms used in Thai utility (PEA/MEA) and EIT documents."
        ),
    },
    "medical": {
        "label": "การแพทย์",
        "desc": "ศัพท์ทางคลินิก คงชื่อยา ขนาดยา ค่าตรวจ ไม่เพิ่มคำแนะนำเอง",
        "temp": 0.15,
        "prompt": (
            "Register: medical/clinical document (patient records, discharge summaries, lab reports, drug information, research). "
            "Use standard clinical terminology; when a Thai lay term is used, give the accepted medical term used in Thailand. "
            "Keep drug names, dosages, units, lab values, ICD codes and abbreviations exactly. "
            "Never add medical advice, interpretation, or content not present in the source. Accuracy over fluency."
        ),
    },
    "legal": {
        "label": "กฎหมาย/สัญญา",
        "desc": "สัญญา ข้อตกลง เอกสารทางกฎหมาย แปลตรงตัว คงเลขข้อ นิยาม คู่สัญญา ไม่ตีความเพิ่ม",
        "temp": 0.1,
        "prompt": (
            "Register: legal document (contracts, agreements, terms and conditions, NDAs, purchase orders, notices, official letters, regulations). "
            "Translate literally and completely; legal accuracy takes priority over fluency. Never summarize, soften, omit or add obligations. "
            "Keep clause and article numbering, defined terms (capitalized terms, terms in quotation marks or brackets), party names, dates, amounts, "
            "currencies, references to laws and sections exactly as in the source. Translate each defined term consistently throughout. "
            "Use formal legal drafting language of the target language "
            "(English: 'shall', 'hereinafter', 'the Parties'; Thai: 'คู่สัญญา', 'ผู้ซื้อ/ผู้ขาย', 'ให้ถือว่า', 'ทั้งนี้', 'เว้นแต่'). "
            "Do not give legal opinions or explanations."
        ),
    },
    "science": {
        "label": "วิทยาศาสตร์และวิศวกรรมศาสตร์",
        "desc": "สำนวนวิชาการ บทความ/รายงานวิจัย คงสมการ ตัวแปร การอ้างอิง",
        "temp": 0.2,
        "prompt": (
            "Register: academic scientific and engineering writing (journal papers, theses, technical reports, abstracts). "
            "Formal, objective, precise; passive voice and nominalization are acceptable where conventional. "
            "Keep equations, variable names, chemical formulas, figure/table references, citations and units exactly. "
            "Use the terminology of the field consistently; keep well-known English technical terms in English inside Thai text when that is standard practice in Thai academic writing."
        ),
    },
}
LEVEL_ORDER = ["general", "email", "engineering", "medical", "science", "legal"]

# ---------------------------------------------------------------- Q&A: ถามโมเดลเกี่ยวกับข้อความหลังแปล (บล็อกแยก ไม่แตะการแปล)
DEFAULT_QUESTIONS = [
    "สรุปใจความสำคัญเป็นข้อๆ",
    "หมายความว่าอะไร อธิบายโดยละเอียด",
    "ตรวจไวยากรณ์และแนะนำการแก้ไข",
    "มีคำศัพท์เทคนิคอะไรบ้าง อธิบายแต่ละคำ",
    "แปลอีกสำนวนที่เป็นทางการกว่า",
    "ร่างคำตอบกลับอีเมลนี้อย่างสุภาพ",
]
QA_MAX_CHARS = 2500      # ตัดข้อความแต่ละส่วนก่อนส่ง เพราะ num_ctx 4096
QA_HISTORY_TURNS = 4     # จำคู่ถาม-ตอบก่อนหน้าเพื่อถามต่อเนื่อง


def build_qa_messages(src_text, src_lang, translation, dst_lang, history, question):
    sys_prompt = (
        "You are a helpful assistant answering questions about a given text and its translation. "
        "Answer in the same language as the question (Thai question -> Thai answer, English question -> English answer). "
        "Be concise and well-structured; use numbered or bullet points when listing. "
        "Base your answer on the given text; if the text does not contain the information, say so briefly instead of guessing. "
        "Do not repeat the whole text back.\n/no_think"
    )
    ctx = f"ข้อความต้นฉบับ ({LANGS.get(src_lang, src_lang)}):\n{(src_text or '')[:QA_MAX_CHARS]}"
    if translation and translation.strip():
        ctx += f"\n\nคำแปล ({LANGS.get(dst_lang, dst_lang)}):\n{translation[:QA_MAX_CHARS]}"
    msgs = [{"role": "system", "content": sys_prompt},
            {"role": "user", "content": ctx},
            {"role": "assistant", "content": "รับทราบ พร้อมตอบคำถามเกี่ยวกับข้อความนี้ครับ"}]
    for q_, a_ in history[-QA_HISTORY_TURNS:]:
        msgs += [{"role": "user", "content": q_}, {"role": "assistant", "content": a_}]
    msgs.append({"role": "user", "content": question})
    return msgs

LANGS = {"th": "Thai", "en": "English"}
THAI_RE = re.compile(r"[฀-๿]")
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def detect_lang(text):
    """ตรวจภาษาต้นทางจากสัดส่วนอักษรไทย"""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "th"
    thai = sum(1 for c in letters if THAI_RE.match(c))
    return "th" if thai / len(letters) > 0.3 else "en"


# ---------------------------------------------------------------- glossary
def load_glossary():
    """อ่าน glossary.txt -> list ของ (level หรือ None, term_th, term_en)"""
    entries = []
    if not os.path.exists(GLOSSARY_FILE):
        return entries
    level = None
    with open(GLOSSARY_FILE, "r", encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^\[(\w+)\]$", line)
            if m:
                level = m.group(1).lower()
                level = None if level in ("all", "global") else level
                continue
            if "=>" not in line:
                continue
            a, b = [s.strip() for s in line.split("=>", 1)]
            if a and b:
                entries.append((level, a, b))
    return entries


def glossary_for(text, src, level, entries):
    """คืนเฉพาะคำศัพท์ที่ปรากฏในข้อความ เพื่อให้ prompt สั้น"""
    low = text.lower()
    hits = []
    for lv, th, en in entries:
        if lv and lv != level:
            continue
        if src == "th" and th in text:
            hits.append((th, en))
        elif src == "en" and en.lower() in low:
            hits.append((en, th))
    return hits[:40]


# ---------------------------------------------------------------- prompt
def build_messages(text, src, dst, level, glossary_hits, variant=False):
    lv = LEVELS[level]
    sys_prompt = (
        f"You are a professional {LANGS[src]}-to-{LANGS[dst]} translator.\n"
        f"Translate the user's text from {LANGS[src]} to {LANGS[dst]}.\n"
        f"{lv['prompt']}\n"
        "Rules:\n"
        "- Output ONLY the translation. No preamble, no notes, no quotes, no explanations.\n"
        "- Preserve line breaks, paragraphs, numbering and bullet formatting of the source.\n"
        "- Do not translate proper names, URLs, emails, code, or product model numbers.\n"
        "- If a sentence is already in the target language, keep it as is.\n"
    )
    if glossary_hits:
        sys_prompt += "Use this terminology exactly:\n" + "\n".join(f"- {a} => {b}" for a, b in glossary_hits) + "\n"
    if variant:
        sys_prompt += "Give an alternative rendering with different wording from a typical first draft, still faithful.\n"
    sys_prompt += "/no_think"
    return [{"role": "system", "content": sys_prompt}, {"role": "user", "content": text}]


# ---------------------------------------------------------------- Ollama
def ollama_get(path, timeout=5):
    with urllib.request.urlopen(OLLAMA_URL + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def list_models():
    try:
        return [m["name"] for m in ollama_get("/api/tags").get("models", [])]
    except Exception:
        return None


def find_ollama_exe():
    """หา ollama.exe: PATH, โฟลเดอร์ติดตั้งมาตรฐาน, หรือชุดพกพาข้างโปรแกรม"""
    import shutil
    cands = [shutil.which("ollama"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
             os.path.join(os.environ.get("ProgramFiles", ""), "Ollama", "ollama.exe"),
             os.path.join(BASE, "ollama", "ollama.exe"),
             os.path.join(BASE, "..", "ollama", "ollama.exe")]
    for c in cands:
        if c and os.path.exists(c):
            return os.path.normpath(c)
    return None


def ensure_ollama(wait_s=25):
    """ถ้าเชื่อมต่อ Ollama ไม่ได้ ให้ลองเปิด 'ollama serve' เอง (ซ่อนหน้าต่าง) แล้วรอจนพร้อม คืน list โมเดลหรือ None"""
    models = list_models()
    if models is not None:
        return models
    exe = find_ollama_exe()
    if not exe:
        return None
    import subprocess
    env = dict(os.environ)
    env.setdefault("OLLAMA_ORIGINS", "*"); env.setdefault("OLLAMA_KEEP_ALIVE", KEEP_ALIVE)
    env.setdefault("OLLAMA_FLASH_ATTENTION", "1"); env.setdefault("OLLAMA_KV_CACHE_TYPE", "q8_0")
    portable_models = os.path.join(os.path.dirname(exe), "..", "models")
    if os.path.isdir(portable_models) and "OLLAMA_MODELS" not in env:
        env["OLLAMA_MODELS"] = os.path.normpath(portable_models)
    try:
        subprocess.Popen([exe, "serve"], env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    for _ in range(wait_s * 2):
        time.sleep(0.5)
        models = list_models()
        if models is not None:
            return models
    return None


def pick_model(available):
    if DEFAULT_MODEL in available:
        return DEFAULT_MODEL
    for cand in [DEFAULT_MODEL] + FALLBACK_MODELS:
        for name in available:
            if name.split(":")[0] == cand.split(":")[0]:
                return name
    return available[0] if available else DEFAULT_MODEL


def stream_chat(model, messages, temperature, stop_event=None):
    """generator: yield ข้อความทีละส่วน; คืน stats ผ่าน StopIteration.value"""
    body = json.dumps({
        "model": model, "messages": messages, "stream": True, "think": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"num_ctx": NUM_CTX, "temperature": temperature, "top_p": 0.9, "repeat_penalty": 1.05},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=body, headers={"Content-Type": "application/json"})
    stats = {}
    try:
        resp = urllib.request.urlopen(req, timeout=600)
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        if "think" in msg:  # โมเดลไม่รับพารามิเตอร์ think -> ส่งใหม่โดยไม่ใส่
            body = json.loads(body.decode("utf-8")); body.pop("think", None)
            req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=600)
        else:
            raise RuntimeError(f"Ollama HTTP {e.code}: {msg[:300]}")
    with resp:
        for line in resp:
            if stop_event is not None and stop_event.is_set():
                break
            if not line.strip():
                continue
            d = json.loads(line.decode("utf-8"))
            if "error" in d:
                raise RuntimeError(d["error"])
            piece = d.get("message", {}).get("content", "")
            if piece:
                yield piece
            if d.get("done"):
                stats = {k: d.get(k) for k in ("eval_count", "eval_duration", "load_duration", "total_duration")}
    return stats


# ---------------------------------------------------------------- ผู้ให้บริการออนไลน์ (OpenAI-compatible) สำรองเมื่อเครื่องไม่มีโมเดลในเครื่อง
API_PRESETS = {
    "OpenTyphoon (SCB10X, ปรับจูนภาษาไทย - แนะนำ)": {
        "base": "https://api.opentyphoon.ai/v1",
        "models": ["typhoon-v2.5-30b-a3b-instruct"],
        "signup": "https://opentyphoon.ai",
        "note": "โมเดล Typhoon ปรับจูนภาษาไทยโดย SCB10X สมัครแล้วสร้าง API key ในหน้า API Keys (คีย์ขึ้นต้น sk-) · ก.ย. 2026 มีโมเดลแชทตัวเดียวคือ typhoon-v2.5-30b-a3b-instruct (v2.1 ถูกปลดแล้ว) กด 'โหลดรายการโมเดล' เพื่อดูตัวล่าสุด"},
    "OpenRouter (หลายโมเดล มีแบบฟรี)": {
        "base": "https://openrouter.ai/api/v1",
        "models": ["google/gemma-4-26b-a4b-it:free", "google/gemma-4-31b-it:free", "qwen/qwen3.8-27b:free", "qwen/qwen3-30b-a3b-instruct-2507", "qwen/qwen3-235b-a22b-2507"],
        "signup": "https://openrouter.ai/keys",
        "note": "ช่องทางเดียวเข้าถึงหลายโมเดล (ภาษาไทยดี: Gemma 4, Qwen3) มีโมเดลฟรี (:free) · ตรวจเมื่อ ก.ย. 2026: ไม่มีโมเดล Typhoon บน OpenRouter แล้ว ถ้าต้องการ Typhoon ให้ใช้ OpenTyphoon โดยตรง · คีย์ต้องขึ้นต้นด้วย sk-or-v1-"},
    "Google Gemini": {
        "base": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite"],
        "signup": "https://aistudio.google.com/apikey",
        "note": "ภาษาไทยดี มีโควตาฟรีใน AI Studio"},
    "Groq (เร็วมาก)": {
        "base": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "qwen/qwen3-32b"],
        "signup": "https://console.groq.com/keys",
        "note": "ความเร็วสูง โมเดลทั่วไป ภาษาไทยพอใช้"},
    "OpenAI": {
        "base": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4.1-mini"],
        "signup": "https://platform.openai.com/api-keys",
        "note": "คุณภาพสูง คิดค่าใช้จ่ายตามโทเค็น"},
    "กำหนดเอง (OpenAI-compatible)": {"base": "", "models": [], "signup": "", "note": "ใส่ Base URL ที่ลงท้ายด้วย /v1 ของบริการที่รองรับรูปแบบ OpenAI"},
}
BACKEND = {"mode": "local", "base": "", "key": "", "model": ""}   # โหมดที่ใช้งานอยู่จริง (ตั้งโดย GUI)


def list_models_openai(base, key, timeout=15):
    req = urllib.request.Request(base.rstrip("/") + "/models", headers={"Authorization": "Bearer " + key, "User-Agent": "LocalTranslator/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    items = d.get("data") if isinstance(d, dict) else d
    return sorted(m.get("id") for m in (items or []) if isinstance(m, dict) and m.get("id"))


def stream_chat_openai(base, key, model, messages, temperature, stop_event=None):
    """generator แบบเดียวกับ stream_chat แต่คุยกับ API รูปแบบ OpenAI (chat/completions, SSE)"""
    msgs = [dict(m, content=m["content"].replace("/no_think", "").rstrip()) for m in messages]
    body = json.dumps({"model": model, "messages": msgs, "stream": True, "temperature": temperature}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key, "User-Agent": "LocalTranslator/1.0",
                                          "HTTP-Referer": "https://localtranslator.local", "X-Title": "Local Translator"})
    try:
        resp = urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        hint = {401: "API key ไม่ถูกต้อง", 402: "เครดิตหมด", 403: "ไม่มีสิทธิ์ใช้โมเดลนี้", 404: "ไม่พบโมเดล/URL", 429: "เกินโควตา ลองใหม่ภายหลัง"}.get(e.code, "")
        raise RuntimeError(f"API {e.code} {hint}: {msg[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"เชื่อมต่อ API ไม่ได้: {e.reason}")
    n = 0; t0 = time.time()
    with resp:
        for raw in resp:
            if stop_event is not None and stop_event.is_set():
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                d = json.loads(data)
            except Exception:
                continue
            if "error" in d:
                raise RuntimeError(str(d["error"]))
            for ch in d.get("choices") or []:
                piece = (ch.get("delta") or {}).get("content") or ""
                if piece:
                    n += 1; yield piece
    return {"eval_count": n, "eval_duration": int((time.time() - t0) * 1e9)}


def pull_model(name, progress_cb=None):
    """ดาวน์โหลดโมเดลเข้า Ollama ผ่าน /api/pull (สตรีมความคืบหน้า) ใช้ได้จากในแอปโดยไม่ต้องเปิด command line"""
    body = json.dumps({"model": name, "stream": True}).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL + "/api/pull", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3600) as resp:
        for line in resp:
            if not line.strip():
                continue
            d = json.loads(line.decode("utf-8"))
            if "error" in d:
                raise RuntimeError(d["error"])
            if progress_cb:
                tot, done = d.get("total") or 0, d.get("completed") or 0
                pct = int(done * 100 / tot) if tot else None
                progress_cb(d.get("status", ""), pct, done, tot)
    return True


def chat_stream(model, messages, temperature, stop_event=None):
    """ตัวเลือกเส้นทาง: โมเดลในเครื่อง (Ollama) หรือ API ออนไลน์ ตาม BACKEND ที่ GUI ตั้งไว้"""
    if BACKEND["mode"] == "api":
        return (yield from stream_chat_openai(BACKEND["base"], BACKEND["key"], BACKEND["model"], messages, temperature, stop_event))
    return (yield from stream_chat(model, messages, temperature, stop_event))


def clean_output(text):
    text = THINK_RE.sub("", text)
    text = text.strip()
    # ตัดคำนำหน้าที่โมเดลบางตัวชอบใส่
    text = re.sub(r"^(Translation|คำแปล)\s*[:：]\s*", "", text, flags=re.I)
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'“”":
        text = text[1:-1].strip()
    return text


def warm_up(model):
    if BACKEND["mode"] == "api":
        return
    try:
        list(stream_chat(model, [{"role": "user", "content": "ok /no_think"}], 0))
    except Exception:
        pass


# ---------------------------------------------------------------- CLI
def run_cli(args):
    models = ensure_ollama()   # เปิด Ollama ให้เองถ้ายังไม่ทำงาน (เหมือนโหมดหน้าต่าง)
    if models is None:
        print("เชื่อมต่อ Ollama ไม่ได้ที่", OLLAMA_URL, "- ติดตั้ง Ollama จาก https://ollama.com/download แล้วลองใหม่", file=sys.stderr)
        return 2
    model = args.model or pick_model(models)
    text = args.text or sys.stdin.read()
    src = args.src or detect_lang(text)
    dst = args.to or ("en" if src == "th" else "th")
    hits = glossary_for(text, src, args.level, load_glossary())
    msgs = build_messages(text, src, dst, args.level, hits)
    print(f"[{model}] {src}->{dst} level={args.level} glossary={len(hits)}", file=sys.stderr)
    out = []
    t0 = time.time()
    gen = stream_chat(model, msgs, LEVELS[args.level]["temp"])
    try:
        while True:
            piece = next(gen)
            out.append(piece)
            sys.stdout.write(piece); sys.stdout.flush()
    except StopIteration as e:
        stats = e.value or {}
    print()
    ev, ed = stats.get("eval_count") or 0, stats.get("eval_duration") or 0
    print(f"[{time.time()-t0:.1f}s, {ev} tok, {ev/(ed/1e9):.1f} tok/s]" if ed else f"[{time.time()-t0:.1f}s]", file=sys.stderr)
    if getattr(args, "ask", None):
        translation = clean_output("".join(out))
        qmsgs = build_qa_messages(text, src, translation, dst, [], args.ask)
        print(f"\n[ask] {args.ask}", file=sys.stderr)
        gen = stream_chat(model, qmsgs, 0.4)
        try:
            while True:
                sys.stdout.write(next(gen)); sys.stdout.flush()
        except StopIteration:
            pass
        print()
    return 0


# ---------------------------------------------------------------- เสียงอ่าน (พอร์ตจาก F:\LocalAI\yt\scripts\generate_audio.py)
def load_replacements():
    """ตารางคำอ่านภาษาอังกฤษ -> ไทย ของโปรเจกต์ yt เช่น Google -> กู-เกิล"""
    try:
        with open(REPLACEMENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def apply_replacements(text, replacements):
    for eng in sorted(replacements.keys(), key=len, reverse=True):
        text = re.sub(r"(?<![A-Za-z])" + re.escape(eng) + r"(?![A-Za-z])", replacements[eng], text, flags=re.IGNORECASE)
    return text


def clean_for_tts(text):
    lines = []
    for line in text.strip().split("\n"):
        line = re.sub(r"\[.*?\]", "", line.strip())
        line = re.sub(r"^[—\-–•*]+\s*", "", line).strip()
        line = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def list_clone_profiles():
    """โปรไฟล์โคลนเสียงใน F:/LocalAI/yt/voices"""
    try:
        if YT_DIR not in sys.path:
            sys.path.insert(0, YT_DIR)
        from scripts.voice_clone import list_voice_profiles
        return list_voice_profiles()
    except Exception:
        return []


def sapi_synthesize(text, voice_name, rate, out_wav):
    """เสียงในเครื่องของ Windows (OneCore เช่น Microsoft Pattara) ผ่าน WinRT ใน PowerShell: ออฟไลน์ เร็วมาก (~0.2 วินาที)
    แต่ธรรมชาติน้อยกว่าเสียง Neural ของ edge-tts"""
    import base64
    import subprocess
    speed = 1.0 + int(rate.replace("%", "").replace("+", "")) / 100.0   # +20% -> 1.2
    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    ps = (
        "Add-Type -AssemblyName System.Runtime.WindowsRuntime;"
        "[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media, ContentType=WindowsRuntime] | Out-Null;"
        "$s=New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer;"
        f"$v=[Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ? {{ $_.DisplayName -like '*{voice_name}*' }} | select -First 1;"
        "if($v){$s.Voice=$v};"
        f"try{{$s.Options.SpeakingRate={speed:.2f}}}catch{{}};"
        f"$op=$s.SynthesizeTextToStreamAsync([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{b64}')));"
        "$m=([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0];"
        "$t=$m.MakeGenericMethod([Windows.Media.SpeechSynthesis.SpeechSynthesisStream]).Invoke($null,@($op));$t.Wait();"
        "$n=[System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($t.Result.GetInputStreamAt(0));"
        f"$f=[System.IO.File]::Create('{out_wav}');$n.CopyTo($f);$f.Close()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=120,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not (os.path.exists(out_wav) and os.path.getsize(out_wav) > 100):
        raise RuntimeError(f"เสียง {voice_name} ในเครื่องไม่ทำงาน")
    return out_wav


def tts_synthesize(text, voice, rate="+0%", pitch="+0Hz", clone_id=None, max_retries=5):
    """สังเคราะห์เสียงเป็นไฟล์ (mp3 หรือ wav ถ้าโคลน) คืน path; วนลองซ้ำเหมือน yt เพราะ edge-tts ล้มเหลวชั่วคราวบ่อย"""
    import asyncio
    import edge_tts
    os.makedirs(TTS_TMP, exist_ok=True)
    import uuid
    stamp = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"   # ไม่ซ้ำแม้สร้างหลายท่อนพร้อมกัน (เดิมชนกันแล้วเปิดไฟล์ไม่ได้)
    out = os.path.join(TTS_TMP, f"tts_{stamp}.mp3")

    if voice.startswith("sapi:"):
        return sapi_synthesize(text, voice[5:], rate, out[:-4] + ".wav")

    async def run():
        last = None
        for attempt in range(max_retries):
            try:
                await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(out)
                if os.path.exists(out) and os.path.getsize(out) > 100:
                    return
            except Exception as e:
                last = e
            await asyncio.sleep(0.4 * (attempt + 1))   # ข้อผิดพลาดชั่วคราวของ edge-tts มักผ่านเมื่อลองซ้ำทันที ไม่ต้องรอนาน
        raise last or RuntimeError("edge-tts ไม่ส่งเสียงกลับมา")
    try:
        asyncio.run(run())
    except Exception:
        # บริการ edge-tts ล่มชั่วคราว -> ใช้เสียงในเครื่องของ Windows แทน เพื่อให้ยังได้ยินเสียง (ปัตตรา/Zira)
        fallback = "Pattara" if voice.startswith("th") else "Zira"
        return sapi_synthesize(text, fallback, rate, out[:-4] + ".wav")
    if clone_id:
        try:
            if YT_DIR not in sys.path:
                sys.path.insert(0, YT_DIR)
            from scripts.voice_clone import get_reference_path, _clone_voice_sync
            ref = get_reference_path(clone_id)
            if ref:
                wav = os.path.join(TTS_TMP, f"tts_{stamp}.wav")
                _clone_voice_sync(out, ref, wav)
                if os.path.exists(wav) and os.path.getsize(wav) > 100:
                    return wav
        except Exception:
            pass
    return out


def split_tts_chunks(text, max_len=140):
    """แบ่งข้อความเป็นท่อนสั้นๆ ตามบรรทัดและประโยค เพื่อเริ่มเล่นท่อนแรกได้เร็วระหว่างสร้างท่อนถัดไป"""
    chunks = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # ตัดที่จุดจบประโยคอังกฤษ หรือช่องว่างของไทย เมื่อยาวเกิน max_len
        parts = re.split(r"(?<=[.!?。])\s+", line)
        for p in parts:
            while len(p) > max_len:
                cut = p.rfind(" ", 0, max_len)
                if cut < max_len // 2:
                    cut = max_len
                chunks.append(p[:cut].strip()); p = p[cut:].strip()
            if p:
                chunks.append(p)
    return chunks


def pop_sentences(buf, final=False, min_len=60, max_len=140):
    """ดึงประโยคที่จบแล้วออกจากบัฟเฟอร์ข้อความที่กำลังสตรีมเข้ามา คืน (รายการประโยค, ส่วนที่เหลือ)
    ตัดที่ขึ้นบรรทัดใหม่, จุดจบประโยคอังกฤษ . ! ? ตามด้วยช่องว่าง, หรือช่องว่างของไทยเมื่อยาวพอ"""
    out = []
    while True:
        m = re.search(r"\n|(?<=[.!?。])\s", buf)
        cut = None
        if m:
            cut = m.start()
        elif len(buf) >= max_len:
            comma = buf.rfind(", ", min_len // 2, max_len)   # ประโยคยาว: ตัดที่จุลภาคก่อน ถ้าไม่มีค่อยตัดที่ช่องว่าง
            sp = buf.rfind(" ", min_len, max_len)
            cut = comma + 1 if comma > 0 else (sp if sp > 0 else max_len)
        elif len(buf) >= min_len and " " in buf[min_len:] and THAI_RE.search(buf):
            cut = buf.index(" ", min_len)     # ไทยไม่มีจุดจบประโยค ใช้ช่องว่างเมื่อยาวพอ; อังกฤษรอเครื่องหมายวรรคตอน
        if cut is None:
            break
        piece, buf = buf[:cut].strip(), buf[cut + 1:] if m and m.group() == "\n" else buf[cut:].lstrip()
        if piece:
            out.append(piece)
        if not buf:
            break
    if final and buf.strip():
        out.append(buf.strip()); buf = ""
    return out, buf


class TtsPipeline:
    """รับข้อความทีละท่อนขณะกำลังแปล สร้างเสียงแบบขนาน (สูงสุด 3 ท่อน) และเล่นตามลำดับทันทีที่ท่อนแรกเสร็จ
    begin() -> feed() ซ้ำได้ -> finish(); stop() หยุดทุกอย่างและทิ้งท่อนที่รอ (เสียงเก่าจะไม่ซ้อนกับเสียงใหม่)
    on_event(kind, msg): 'status' ระหว่างทำงาน, 'done' เมื่อจบ, 'error' เมื่อผิดพลาด"""
    def __init__(self, on_event):
        self.on_event = on_event
        self.stop_event = threading.Event()
        self.thread = None
        self.player = Player()
        self.pool = None
        self.jobs = None
        self.count = 0

    @property
    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def begin(self, voice, rate, clone_id=None):
        from concurrent.futures import ThreadPoolExecutor
        self.stop()
        self.stop_event = threading.Event()
        self.voice, self.rate, self.clone_id = voice, rate, clone_id
        self.pool = ThreadPoolExecutor(max_workers=3)
        self.jobs = queue.Queue()
        self.count = 0
        ev, jobs, pool = self.stop_event, self.jobs, self.pool

        def run():
            played = 0
            try:
                while not ev.is_set():
                    fut = jobs.get()
                    if fut is None:
                        break
                    path = fut.result()
                    if ev.is_set():
                        break
                    played += 1
                    self.on_event("status", f"กำลังอ่านท่อนที่ {played} ...")
                    self.player.play(path)
                    while self.player.is_playing() and not ev.is_set():
                        time.sleep(0.1)
                    self.player.stop()
                if not ev.is_set():
                    self.on_event("done", f"อ่านเสียงจบแล้ว ({played} ท่อน)")
            except Exception as e:
                self.player.stop()
                self.on_event("error", str(e))
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
        self.thread = threading.Thread(target=run, daemon=True); self.thread.start()

    def feed(self, text):
        if self.jobs is None or self.stop_event.is_set() or not text.strip():
            return
        self.count += 1
        self.jobs.put(self.pool.submit(tts_synthesize, text, self.voice, self.rate, "+0Hz", self.clone_id))

    def finish(self):
        if self.jobs is not None:
            self.jobs.put(None)

    def stop(self):
        self.stop_event.set()
        if self.jobs is not None:
            self.jobs.put(None)
        try:
            self.player.stop()
        except Exception:
            pass


class Player:
    """เล่นไฟล์เสียงด้วย MCI ของ Windows (winmm) ไม่ต้องลง library"""
    def __init__(self):
        self.mci = ctypes.windll.winmm.mciSendStringW
        self.alias = None

    def play(self, path):
        self.stop()
        alias = "tts" + str(int(time.time() * 1000) % 100000)
        typ = "waveaudio" if path.lower().endswith(".wav") else "mpegvideo"
        rc = 1
        for _ in range(4):   # ไฟล์อาจยังถูกปิดไม่เสร็จ ลองซ้ำสั้นๆ
            rc = self.mci(f'open "{path}" type {typ} alias {alias}', None, 0, None)
            if rc == 0:
                break
            time.sleep(0.3)
        if rc != 0:
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(rc, buf, 256)
            raise RuntimeError(f"เปิดไฟล์เสียงไม่ได้ ({buf.value.strip() or rc}): {os.path.basename(path)}")
        self.alias = alias
        self.mci(f"play {alias}", None, 0, None)

    def is_playing(self):
        if not self.alias:
            return False
        buf = ctypes.create_unicode_buffer(64)
        self.mci(f"status {self.alias} mode", buf, 64, None)
        return buf.value == "playing"

    def stop(self):
        if self.alias:
            self.mci(f"stop {self.alias}", None, 0, None)
            self.mci(f"close {self.alias}", None, 0, None)
            self.alias = None


# ---------------------------------------------------------------- Windows: คีย์ลัด + ตรวจการลากคลุมข้อความ (ctypes ล้วน)
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
WM_HOTKEY, WH_MOUSE_LL = 0x0312, 14
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_MBUTTONDOWN = 0x0201, 0x0202, 0x0204, 0x0207
VK_CONTROL, VK_MENU, VK_C, KEYEVENTF_KEYUP = 0x11, 0x12, 0x43, 0x0002
GA_ROOT, GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = 2, -20, 0x08000000, 0x00000080


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", POINT), ("mouseData", ctypes.c_uint), ("flags", ctypes.c_uint),
                ("time", ctypes.c_uint), ("dwExtraInfo", ctypes.c_size_t)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint), ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_ssize_t), ("time", ctypes.c_uint), ("pt", POINT)]


HOOKPROC = ctypes.CFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t)
_hook_ref = {}  # กัน GC เก็บ callback


def win_event_thread(on_hotkey, on_select, on_click_elsewhere, is_own_window, status_cb):
    """เธรดเดียวรับทั้ง hotkey และ mouse hook (ทั้งสองต้องอยู่กับ message loop ของเธรดที่ติดตั้ง)
    on_select(x, y) ถูกเรียกเมื่อผู้ใช้ลากเมาส์ (เลือกข้อความ) หรือดับเบิลคลิก ในหน้าต่างที่ไม่ใช่ของเรา"""
    user32 = ctypes.windll.user32
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p, ctypes.c_uint]
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    hot_ok = None  # ลอง Ctrl+Alt+T ก่อน ถ้าโปรแกรมอื่นจองไว้ให้ใช้ Ctrl+Alt+Y แทน
    for key in ("T", "Y"):
        if user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord(key)):
            hot_ok = "Ctrl+Alt+" + key; break
    state = {"down": None, "last_down": (0, 0, 0)}
    dbl_ms = user32.GetDoubleClickTime()

    def proc(nCode, wParam, lParam):
        if nCode >= 0:
            try:
                info = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                x, y, t = info.pt.x, info.pt.y, info.time
                if wParam == WM_LBUTTONDOWN:
                    own = is_own_window(user32.GetForegroundWindow(), x, y)
                    if not own:
                        on_click_elsewhere()
                    lx, ly, lt = state["last_down"]
                    state["last_down"] = (x, y, t)
                    state["down"] = None if own else (x, y, t)
                    if not own and t - lt <= dbl_ms and abs(x - lx) < 6 and abs(y - ly) < 6:
                        state["down"] = None
                        on_select(x, y)           # ดับเบิลคลิกเลือกคำ
                elif wParam == WM_LBUTTONUP:
                    d = state["down"]; state["down"] = None
                    if d and (abs(x - d[0]) > 14 or abs(y - d[1]) > 14) and not is_own_window(user32.GetForegroundWindow(), x, y):
                        on_select(x, y)           # ลากคลุม
                elif wParam in (WM_RBUTTONDOWN, WM_MBUTTONDOWN):
                    on_click_elsewhere()
            except Exception:
                pass
        return user32.CallNextHookEx(None, nCode, wParam, lParam)

    cb = HOOKPROC(proc); _hook_ref["cb"] = cb
    hook = user32.SetWindowsHookExW(WH_MOUSE_LL, cb, None, 0)
    status_cb(hot_ok, bool(hook))
    msg = MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == WM_HOTKEY:
            on_hotkey()


def build_float_frames(size, n, key_color):
    """สร้างเฟรมหุ่นยนต์ n สี (วนตามวงล้อสี) บนพื้นสีคีย์ สำหรับไอคอนลอยแบบโปร่งใส คืน list ของ tk.PhotoImage"""
    try:
        import base64
        import colorsys
        import io
        import tkinter as tk
        from PIL import Image
        sys.path.insert(0, BASE)
        from make_icon import draw_robot
        key = tuple(int(key_color[i:i + 2], 16) for i in (1, 3, 5))
        out = []
        for i in range(n):
            r, g, b = colorsys.hsv_to_rgb(i / n, 0.75, 1.0)
            col = (int(r * 255), int(g * 255), int(b * 255), 255)
            im = draw_robot(256, bg=False, accent=col, glow=col).resize((size, size), Image.LANCZOS)
            bgim = Image.new("RGBA", (size, size), key + (255,)); bgim.alpha_composite(im)
            buf = io.BytesIO(); bgim.convert("RGB").save(buf, format="PNG")
            out.append(tk.PhotoImage(data=base64.b64encode(buf.getvalue())))
        return out
    except Exception:
        return []


def make_noactivate(hwnd):
    """ให้หน้าต่างลอยไม่แย่งโฟกัส (ข้อความที่เลือกในโปรแกรมอื่นจะยังถูกเลือกอยู่ตอนคลิกไอคอน)"""
    user32 = ctypes.windll.user32
    user32.GetWindowLongW.restype = ctypes.c_long
    root_hwnd = user32.GetAncestor(hwnd, GA_ROOT)
    for h in {hwnd, root_hwnd}:
        style = user32.GetWindowLongW(h, GWL_EXSTYLE)
        user32.SetWindowLongW(h, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    return root_hwnd


def send_ctrl_c():
    """ปล่อย Alt ที่ผู้ใช้กดค้าง แล้วส่ง Ctrl+C ไปยังหน้าต่างที่โฟกัสอยู่"""
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    user32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


# ---------------------------------------------------------------- GUI
MUTEX_NAME = "Local\\ThaiLocalTranslator.single"


def acquire_single_instance():
    """กันเปิดซ้อนหลายชุด (ทำให้ไอคอนลอยหลายตัวและเสียงอ่านซ้อนกัน) ถ้ามีอยู่แล้วให้ดึงหน้าต่างเดิมขึ้นมาแทน"""
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW.restype = ctypes.c_void_p
    handle = k32.CreateMutexW(None, False, MUTEX_NAME)
    if k32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        u = ctypes.windll.user32
        u.FindWindowW.restype = ctypes.c_void_p
        h = u.FindWindowW(None, "Local Translator - แปลภาษาด้วยโมเดลในเครื่อง")
        if h:
            u.ShowWindow(ctypes.c_void_p(h), 9)
            u.keybd_event(VK_MENU, 0, 0, 0); u.SetForegroundWindow(ctypes.c_void_p(h)); u.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        return False
    return handle


def run_gui(minimized=False):
    import tkinter as tk
    from tkinter import ttk, font as tkfont, messagebox

    if not acquire_single_instance():
        return

    # ให้พิกัดของ mouse hook (พิกเซลจริง) ตรงกับพิกัดของ Tk บนจอที่ตั้ง scaling 125/150%
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", ctypes.windll.user32.GetDpiForSystem() / 72.0)
    except Exception:
        pass
    root.title("Local Translator - แปลภาษาด้วยโมเดลในเครื่อง")
    root.geometry("1240x800")
    root.minsize(720, 520)
    for ico in (os.path.join(BASE, "translator.ico"), os.path.join(BASE, "..", "lung_pee.ico")):
        try:
            root.iconbitmap(ico); break
        except Exception:
            continue

    fams = set(tkfont.families())
    fam = next((f for f in ("Sarabun", "Leelawadee UI", "Segoe UI", "Tahoma") if f in fams), "TkDefaultFont")
    ui_font = (fam, 11)
    text_font = (fam, 13)
    small_font = (fam, 9)
    root.option_add("*Font", ui_font)
    style = ttk.Style(root)
    try:
        style.theme_use("vista")
    except Exception:
        pass
    style.configure("TButton", padding=(10, 5))
    style.configure("Big.TButton", padding=(16, 8), font=(fam, 11, "bold"))

    # ---------- state
    settings = {"level": "general", "direction": "auto", "topmost": False, "clipwatch": False, "model": "",
                "floaticon": True, "autospeak": False, "ttsVoice": "เปรมวดี (หญิง)", "ttsRate": "ปกติ",
                "questions": list(DEFAULT_QUESTIONS), "qaOpen": False, "qaAutoSpeak": False,
                "api": {"mode": "auto", "preset": "OpenTyphoon (SCB10X, ปรับจูนภาษาไทย - แนะนำ)", "base": "", "key": "", "model": ""}}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except Exception:
        pass
    if not isinstance(settings.get("questions"), list):
        settings["questions"] = list(DEFAULT_QUESTIONS)
    settings["questions"] = [str(x).strip() for x in settings["questions"] if str(x).strip()]
    history = []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        pass
    glossary = load_glossary()
    q = queue.Queue()
    worker = {"thread": None, "stop": threading.Event(), "busy": False}
    st = {"models": [], "model": "", "last_result": "", "last_clip": None, "hotkey_ok": None}

    def save_settings():
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def save_history():
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history[-MAX_HISTORY:], f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    # ---------- เปิดอัตโนมัติเมื่อเปิดเครื่อง (ทางลัดในโฟลเดอร์ Startup)
    def startup_lnk():
        return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "Local Translator.lnk")

    def autostart_enabled():
        return os.path.exists(startup_lnk())

    def set_autostart(enable):
        import subprocess
        lnk = startup_lnk()
        if not enable:
            try:
                os.remove(lnk)
            except Exception:
                pass
            set_status("ยกเลิกเปิดอัตโนมัติแล้ว"); return
        if FROZEN:
            target, args = sys.executable, "--minimized"
        else:
            # รันจากซอร์สโค้ด (ไม่มี Translate.bat แล้ว): เปิดด้วย pythonw.exe ตรง ๆ ไม่มีหน้าต่างคอนโซล
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            target = pyw if os.path.exists(pyw) else sys.executable
            args = f'"{os.path.abspath(__file__)}" --minimized'
        ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');$s.TargetPath='{target}';$s.Arguments='{args}';"
              f"$s.WorkingDirectory='{BASE}';$s.IconLocation='{os.path.join(BASE, 'translator.ico')},0';$s.WindowStyle=7;"
              f"$s.Description='Local Translator autostart';$s.Save()")
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            set_status("ตั้งเปิดอัตโนมัติเมื่อเปิดเครื่องแล้ว (Startup)" if os.path.exists(lnk) else "สร้างทางลัด Startup ไม่สำเร็จ")
        except Exception as e:
            set_status("สร้างทางลัด Startup ไม่สำเร็จ: " + str(e))

    # ==================== เลย์เอาต์มาตรฐาน ====================
    # หลักการ: (1) ทุกแถวปุ่ม/ตัวเลือกใช้ Flow = ไหลลงบรรทัดใหม่เมื่อความกว้างไม่พอ ไม่มีปุ่มถูกตัด
    #          (2) แถบสถานะ แถวปุ่ม และแผงถามโมเดล จองพื้นที่ด้านล่างก่อน ช่องข้อความรับพื้นที่ที่เหลือ
    #          (3) ส่วน "ตัวเลือก" และ "ถามโมเดล" ย่อ/ขยายได้ด้วยปุ่มของตัวเอง โปรแกรมจำสถานะไว้
    class Flow(ttk.Frame):
        """เฟรมจัดวิดเจ็ตแบบไหล: เรียงซ้ายไปขวา เต็มความกว้างแล้วขึ้นบรรทัดใหม่"""
        def __init__(self, master, padding=(0, 0, 0, 0), **kw):
            super().__init__(master, **kw)
            p = padding if isinstance(padding, (tuple, list)) else (padding,) * 4
            self.pad = (p + p)[:4] if len(p) < 4 else tuple(p[:4])     # (ซ้าย, บน, ขวา, ล่าง)
            self.items = []; self._pending = None; self._last = None
            self.bind("<Configure>", lambda e: self.schedule())
            master.bind("<Configure>", lambda e: self.schedule(), add="+")

        def add(self, w, padx=(0, 6), pady=(0, 4)):
            self.items.append((w, padx, pady)); self.schedule(); return w

        def clear(self):
            for w, _, _ in self.items:
                w.destroy()
            self.items = []; self._last = None

        def schedule(self):
            if self._pending is None:
                self._pending = self.after_idle(self.relayout)

        def relayout(self):
            """วางด้วย place ทีละชิ้น (ไม่ใช้ grid เพราะคอลัมน์จะยืดตามชิ้นที่กว้างสุด ทำให้ตำแหน่งจริงล้นขอบ)"""
            self._pending = None
            top = self.winfo_toplevel()
            if top.winfo_width() < 50:
                return
            # พื้นที่ที่ใช้ได้ = ขอบขวาของหน้าต่าง - ตำแหน่งซ้ายของเฟรมนี้ (พาเรนต์อาจ "ขอ" กว้างเกินหน้าต่าง จึงไม่ใช้ความกว้างพาเรนต์)
            width = top.winfo_width() - (self.winfo_rootx() - top.winfo_rootx()) - 20 - self.pad[0] - self.pad[2]
            if self.winfo_width() > 50:
                width = min(width, self.winfo_width() - self.pad[0] - self.pad[2])
            x = y = row_h = 0; plan = []
            for w, padx, pady in self.items:
                rw, rh = w.winfo_reqwidth(), w.winfo_reqheight()
                need = rw + padx[0] + padx[1]
                if x > 0 and x + need > width:
                    x = 0; y += row_h; row_h = 0
                plan.append((w, self.pad[0] + x + padx[0], self.pad[1] + y + pady[0]))
                x += need; row_h = max(row_h, rh + pady[0] + pady[1])
            total_h = self.pad[1] + y + row_h + self.pad[3]
            key = (tuple((id(w), px, py) for w, px, py in plan), total_h)
            if key == self._last:
                return
            self._last = key
            for w, px, py in plan:
                w.place(x=px, y=py)
            self.configure(height=total_h)

    # ---------- แถบสถานะ (จองที่ล่างสุดก่อนทุกส่วน)
    status_bar = Flow(root, padding=(10, 2, 10, 6)); status_bar.pack(fill="x", side="bottom")
    status_var = tk.StringVar(value="กำลังเชื่อมต่อ Ollama ...")
    status_bar.add(ttk.Label(status_bar, textvariable=status_var, font=small_font, foreground="#444"), padx=(0, 20))
    hotkey_var = tk.StringVar(value="")
    status_bar.add(ttk.Label(status_bar, textvariable=hotkey_var, font=small_font, foreground="#0E6B5B"))

    def set_status(msg):
        status_var.set(msg)

    # กล่องล่าง = แถวปุ่มหลัก + แผงถามโมเดล จองพื้นที่ต่อจากแถบสถานะ (ช่องข้อความเป็นส่วนเดียวที่หดเมื่อหน้าต่างเล็ก)
    bottom_box = ttk.Frame(root); bottom_box.pack(side="bottom", fill="x")

    # ---------- แถวหัว: ย่อ/ขยายตัวเลือก · สรุประดับที่เลือก · ประวัติ · glossary
    hdr = Flow(root, padding=(10, 6, 10, 0)); hdr.pack(fill="x", before=bottom_box)   # ลำดับจองพื้นที่: แถบสถานะ, แถวหัว, กล่องล่าง(ปุ่ม+ถามโมเดล), ตัวเลือก, ช่องข้อความ(หดได้)
    opts_btn = ttk.Button(hdr, text="▾ ตัวเลือก", command=lambda: toggle_opts()); hdr.add(opts_btn)
    level_summary = tk.StringVar()
    hdr.add(ttk.Label(hdr, textvariable=level_summary, font=small_font, foreground="#555"), padx=(0, 16))
    hist_btn = ttk.Button(hdr, text="ประวัติ ▾", command=lambda: toggle_history()); hdr.add(hist_btn)
    hdr.add(ttk.Button(hdr, text="glossary", command=lambda: os.startfile(GLOSSARY_FILE) if os.path.exists(GLOSSARY_FILE) else None))
    hdr.add(ttk.Button(hdr, text="⚙ ผู้ให้บริการ", command=lambda: open_provider_dialog()), padx=(12, 6))

    # ---------- ส่วนตัวเลือก (ย่อ/ขยายได้)
    opts = ttk.Frame(root, padding=(10, 2, 10, 2))
    lf = ttk.LabelFrame(opts, text=" ระดับการแปล ", padding=(8, 2)); lf.pack(fill="x")
    lvl_flow = Flow(lf); lvl_flow.pack(fill="x")
    level_var = tk.StringVar(value=settings["level"] if settings["level"] in LEVELS else "general")
    for key in LEVEL_ORDER:
        lvl_flow.add(ttk.Radiobutton(lvl_flow, text=LEVELS[key]["label"], value=key, variable=level_var,
                                     command=lambda: (settings.update(level=level_var.get()), save_settings(), show_desc())), padx=(0, 14))
    desc_var = tk.StringVar()
    desc_lbl = ttk.Label(lf, textvariable=desc_var, font=small_font, foreground="#555", wraplength=900, justify="left"); desc_lbl.pack(anchor="w")
    lf.bind("<Configure>", lambda e: desc_lbl.configure(wraplength=max(300, e.width - 30)))

    def show_desc():
        desc_var.set(LEVELS[level_var.get()]["desc"])
        level_summary.set("ระดับ: " + LEVELS[level_var.get()]["label"])
    show_desc()

    row2 = Flow(opts); row2.pack(fill="x", pady=(4, 0))
    f_dir = ttk.Frame(row2); ttk.Label(f_dir, text="ทิศทาง:").pack(side="left")
    DIRS = [("auto", "ตรวจอัตโนมัติ (ไทย ⇄ อังกฤษ)"), ("th2en", "ไทย → อังกฤษ"), ("en2th", "อังกฤษ → ไทย")]
    dir_var = tk.StringVar(value=dict(DIRS).get(settings["direction"], DIRS[0][1]))
    dir_cb = ttk.Combobox(f_dir, textvariable=dir_var, values=[d[1] for d in DIRS], state="readonly", width=26); dir_cb.pack(side="left", padx=(4, 0))
    dir_cb.bind("<<ComboboxSelected>>", lambda e: (settings.update(direction=next(k for k, v in DIRS if v == dir_var.get())), save_settings()))
    row2.add(f_dir, padx=(0, 16))
    f_model = ttk.Frame(row2); ttk.Label(f_model, text="โมเดล:").pack(side="left")
    model_var = tk.StringVar(value="กำลังเชื่อมต่อ Ollama...")
    model_cb = ttk.Combobox(f_model, textvariable=model_var, state="readonly", width=36); model_cb.pack(side="left", padx=(4, 0))
    row2.add(f_model)

    API_TAG = "☁ "   # รายการโมเดลออนไลน์ในช่องโมเดลขึ้นต้นด้วยเครื่องหมายนี้

    def api_configured():
        a = settings.get("api") or {}
        return bool(a.get("base") and a.get("key") and a.get("model"))

    def use_backend(mode):
        """สลับเส้นทางที่ใช้จริง: 'local' หรือ 'api'"""
        a = settings.get("api") or {}
        BACKEND.update(mode=mode, base=a.get("base", ""), key=a.get("key", ""), model=a.get("model", ""))
        st["backend"] = mode
        if mode == "api":
            st["model"] = a.get("model", "")   # ให้ปุ่มแปล/ถามผ่านการตรวจ "มีโมเดล" (chat_stream ใช้ BACKEND['model'] เอง)

    def on_model_change(_=None):
        name = model_var.get()
        if name.startswith(API_TAG):
            use_backend("api"); settings["model"] = name; save_settings()
            set_status(f"ใช้โมเดลออนไลน์ {BACKEND['model']} ผ่าน API"); return
        use_backend("local")
        st["model"] = name; settings["model"] = name; save_settings()
        threading.Thread(target=warm_up, args=(st["model"],), daemon=True).start()
        set_status(f"กำลังโหลด {st['model']} เข้า GPU ...")
    model_cb.bind("<<ComboboxSelected>>", on_model_change)

    row3 = Flow(opts); row3.pack(fill="x", pady=(2, 0))
    topmost_var = tk.BooleanVar(value=settings["topmost"])
    clip_var = tk.BooleanVar(value=settings["clipwatch"])
    float_var = tk.BooleanVar(value=settings["floaticon"])
    auto_var = tk.BooleanVar(value=autostart_enabled())

    def apply_topmost():
        root.attributes("-topmost", topmost_var.get()); settings["topmost"] = topmost_var.get(); save_settings()
    row3.add(ttk.Checkbutton(row3, text="อยู่บนสุดเสมอ", variable=topmost_var, command=apply_topmost), padx=(0, 12))
    row3.add(ttk.Checkbutton(row3, text="เฝ้าคลิปบอร์ด (แปลเองทุกครั้งที่กด Ctrl+C)", variable=clip_var,
                             command=lambda: (settings.update(clipwatch=clip_var.get()), save_settings())), padx=(0, 12))
    row3.add(ttk.Checkbutton(row3, text="ไอคอนลอยเมื่อลากคลุมข้อความ (คลิกไอคอนแล้วแปล)", variable=float_var,
                             command=lambda: (settings.update(floaticon=float_var.get()), save_settings())), padx=(0, 12))
    row3.add(ttk.Checkbutton(row3, text="เปิดอัตโนมัติเมื่อเปิดเครื่อง", variable=auto_var,
                             command=lambda: set_autostart(auto_var.get())))

    def toggle_opts(force=None):
        want = (not settings.get("optsOpen", True)) if force is None else force
        settings["optsOpen"] = want; save_settings()
        if want:
            opts.pack(fill="x", after=bottom_box); opts_btn.config(text="▴ ตัวเลือก")   # อยู่ใต้แถวหัว แต่จองพื้นที่หลังกล่องล่าง (หน้าต่างเตี้ยจะหดตัวเลือกก่อนปุ่มหลัก)
        else:
            opts.pack_forget(); opts_btn.config(text="▾ ตัวเลือก")
    toggle_opts(settings.get("optsOpen", True))

    # ---------- แถวปุ่มหลัก (จองที่ด้านล่าง เหนือแถบสถานะ ไหลลงบรรทัดใหม่ได้)
    btns = Flow(bottom_box, padding=(10, 6, 10, 2)); btns.pack(fill="x")
    translate_btn = ttk.Button(btns, text="แปล  (Ctrl+Enter)", style="Big.TButton", command=lambda: start_translate()); btns.add(translate_btn)
    stop_btn = ttk.Button(btns, text="หยุด", command=lambda: (worker["stop"].set(), stop_speech(), set_status("หยุดแล้ว"))); btns.add(stop_btn)  # หยุดทั้งการแปลและเสียงอ่าน ใช้ได้ตลอด
    btns.add(ttk.Button(btns, text="แปลอีกสำนวน", command=lambda: start_translate(variant=True)))
    btns.add(ttk.Button(btns, text="⇄ สลับ", command=lambda: swap()))
    btns.add(ttk.Button(btns, text="วาง+แปล", command=lambda: paste_and_translate()))
    btns.add(ttk.Button(btns, text="คัดลอก", command=lambda: copy_result()))
    btns.add(ttk.Button(btns, text="ล้าง", command=lambda: (src.delete("1.0", "end"), dst.delete("1.0", "end"))))
    qa_btn = ttk.Button(btns, text="❓ ถามโมเดล ▾", style="Big.TButton", command=lambda: toggle_qa()); btns.add(qa_btn, padx=(12, 0))

    # ---------- ช่องข้อความซ้าย-ขวา (รับพื้นที่ที่เหลือ ลากเส้นแบ่งกลางได้)
    pane = ttk.PanedWindow(root, orient="horizontal"); pane.pack(fill="both", expand=True, padx=10, pady=(4, 0))
    left = ttk.Frame(pane, padding=(0, 0, 4, 0)); right = ttk.Frame(pane, padding=(4, 0, 0, 0))
    pane.add(left, weight=1); pane.add(right, weight=1)

    src_lbl = tk.StringVar(value="ข้อความต้นทาง")
    ttk.Label(left, textvariable=src_lbl, font=(fam, 10, "bold")).pack(anchor="w")
    src = tk.Text(left, wrap="word", font=text_font, undo=True, padx=8, pady=6, relief="solid", borderwidth=1, height=3, width=20)
    src.pack(fill="both", expand=True)
    dst_lbl = tk.StringVar(value="คำแปล")
    ttk.Label(right, textvariable=dst_lbl, font=(fam, 10, "bold")).pack(anchor="w")
    tts_row = Flow(right, padding=(0, 6, 0, 0)); tts_row.pack(side="bottom", fill="x")   # แถวเสียงอยู่ใต้ช่องคำแปลเสมอ
    dst = tk.Text(right, wrap="word", font=text_font, padx=8, pady=6, relief="solid", borderwidth=1, background="#F7F8F4", height=3, width=20)
    dst.pack(fill="both", expand=True)

    # ---------- แถวเสียงอ่าน (ฟังก์ชันจากโปรเจกต์ yt)
    tts_row.add(ttk.Button(tts_row, text="🔊 อ่านคำแปล", command=lambda: speak_text(dst.get("1.0", "end"))), padx=(0, 4))
    tts_row.add(ttk.Button(tts_row, text="⏹", width=3, command=lambda: stop_speech()), padx=(0, 8))
    voice_names = list(TTS_VOICES.keys())
    clone_profiles = list_clone_profiles()
    voice_names += [f"โคลน: {p.get('name', p['id'])}" for p in clone_profiles]
    clone_ids = {f"โคลน: {p.get('name', p['id'])}": p["id"] for p in clone_profiles}
    tts_voice_var = tk.StringVar(value=settings["ttsVoice"] if settings["ttsVoice"] in voice_names else voice_names[0])
    vcb = ttk.Combobox(tts_row, textvariable=tts_voice_var, values=voice_names, state="readonly", width=15); tts_row.add(vcb, padx=(0, 4))
    vcb.bind("<<ComboboxSelected>>", lambda e: (settings.update(ttsVoice=tts_voice_var.get()), save_settings()))
    tts_rate_var = tk.StringVar(value=settings["ttsRate"] if settings["ttsRate"] in TTS_RATES else "ปกติ")
    rcb = ttk.Combobox(tts_row, textvariable=tts_rate_var, values=list(TTS_RATES.keys()), state="readonly", width=7); tts_row.add(rcb)
    rcb.bind("<<ComboboxSelected>>", lambda e: (settings.update(ttsRate=tts_rate_var.get()), save_settings()))
    autospeak_var = tk.BooleanVar(value=settings["autospeak"])
    tts_row.add(ttk.Checkbutton(tts_row, text="อ่านอัตโนมัติ", variable=autospeak_var,
                                command=lambda: (settings.update(autospeak=autospeak_var.get()), save_settings())))

    # ---------- history panel (ซ่อนได้)
    hist_frame = ttk.Frame(root, padding=(10, 0, 10, 6))
    hist_list = tk.Listbox(hist_frame, height=6, font=small_font, activestyle="none")
    hist_list.pack(side="left", fill="both", expand=True)
    hsb = ttk.Scrollbar(hist_frame, command=hist_list.yview); hsb.pack(side="right", fill="y")
    hist_list.config(yscrollcommand=hsb.set)
    hist_shown = {"on": False}

    def refresh_history():
        hist_list.delete(0, "end")
        for h in reversed(history[-60:]):
            s = h["src"].replace("\n", " ")[:60]; d = h["dst"].replace("\n", " ")[:60]
            hist_list.insert("end", f"[{LEVELS.get(h.get('level'), LEVELS['general'])['label']}] {s}  →  {d}")

    def toggle_history():
        hist_shown["on"] = not hist_shown["on"]
        if hist_shown["on"]:
            refresh_history(); hist_frame.pack(side="bottom", fill="x", padx=10, pady=(0, 6), before=bottom_box); hist_btn.config(text="ประวัติ ▴")
        else:
            hist_frame.pack_forget(); hist_btn.config(text="ประวัติ ▾")

    def load_history_item(_=None):
        sel = hist_list.curselection()
        if not sel:
            return
        h = list(reversed(history[-60:]))[sel[0]]
        src.delete("1.0", "end"); src.insert("1.0", h["src"])
        dst.delete("1.0", "end"); dst.insert("1.0", h["dst"])
    hist_list.bind("<Double-Button-1>", load_history_item)

    # ==================== Q&A: ถามโมเดลเกี่ยวกับข้อความหลังแปล (บล็อกแยก ปิดเป็นค่าเริ่มต้น) ====================
    qa = {"busy": False, "stop": threading.Event(), "history": [], "open": False, "edit": False, "question": ""}
    qa_frame = ttk.LabelFrame(bottom_box, text=" ถามโมเดลเกี่ยวกับข้อความนี้ ", padding=(10, 4))
    pills = Flow(qa_frame); pills.pack(fill="x")
    qa_row = Flow(qa_frame); qa_row.pack(fill="x", pady=(4, 2))
    qa_inp = ttk.Entry(qa_row, width=48); qa_row.add(qa_inp, padx=(0, 8))
    qa_ask_btn = ttk.Button(qa_row, text="ถาม", command=lambda: ask_question(qa_inp.get())); qa_row.add(qa_ask_btn)
    qa_row.add(ttk.Button(qa_row, text="+ บันทึกเป็นปุ่ม", command=lambda: add_question(qa_inp.get())))
    qa_edit_btn = ttk.Button(qa_row, text="แก้ไขปุ่ม", command=lambda: toggle_qa_edit()); qa_row.add(qa_edit_btn)
    qa_bar = Flow(qa_frame); qa_bar.pack(fill="x", pady=(4, 0), side="bottom")   # แถวปุ่มอยู่ล่างสุดเสมอ ไม่ถูกช่องคำตอบดันหลุด
    qa_out = tk.Text(qa_frame, wrap="word", font=text_font, padx=8, pady=6, relief="solid", borderwidth=1, height=4, width=20, background="#F4F6FB")
    qa_out.pack(fill="both", expand=True)
    qa_stop_btn = ttk.Button(qa_bar, text="หยุด", command=lambda: (qa["stop"].set(), stop_speech(), set_status("หยุดแล้ว"))); qa_bar.add(qa_stop_btn)  # หยุดทั้งคำตอบและเสียงอ่าน ใช้ได้ตลอด
    qa_bar.add(ttk.Button(qa_bar, text="🔊 อ่านคำตอบ", command=lambda: speak_text(qa_out.get("1.0", "end"))))
    qa_bar.add(ttk.Button(qa_bar, text="คัดลอกคำตอบ", command=lambda: (root.clipboard_clear(), root.clipboard_append(qa_out.get("1.0", "end").strip()), set_status("คัดลอกคำตอบแล้ว"))))
    qa_bar.add(ttk.Button(qa_bar, text="ล้างบทสนทนา", command=lambda: (qa_reset(), qa_out.delete("1.0", "end"))))
    qa_speak_var = tk.BooleanVar(value=settings["qaAutoSpeak"])
    qa_bar.add(ttk.Checkbutton(qa_bar, text="อ่านคำตอบอัตโนมัติ", variable=qa_speak_var,
                               command=lambda: (settings.update(qaAutoSpeak=qa_speak_var.get()), save_settings())))
    qa_size_btn = ttk.Button(qa_bar, text="ขยายช่องคำตอบ ▴", command=lambda: toggle_qa_size()); qa_bar.add(qa_size_btn, padx=(12, 6))
    qa_hint = ttk.Label(qa_bar, text="", font=small_font, foreground="#555"); qa_bar.add(qa_hint)
    pill_widgets = []

    def toggle_qa_size():
        big = qa_out.cget("height") <= 4
        qa_out.configure(height=12 if big else 4)
        qa_size_btn.config(text="ย่อช่องคำตอบ ▾" if big else "ขยายช่องคำตอบ ▴")

    def render_question_pills():
        pills.clear(); pill_widgets.clear()
        for i, qtext in enumerate(settings["questions"]):
            if qa["edit"]:
                b = ttk.Button(pills, text="× " + qtext, command=lambda i=i: delete_question(i))
            else:
                b = ttk.Button(pills, text=qtext, command=lambda t=qtext: ask_question(t))
            pills.add(b); pill_widgets.append(b)
        if qa["edit"]:
            b = ttk.Button(pills, text="คืนค่าเริ่มต้น", command=lambda: (settings.update(questions=list(DEFAULT_QUESTIONS)), save_settings(), render_question_pills()))
            pills.add(b); pill_widgets.append(b)
        if not settings["questions"] and not qa["edit"]:
            pills.add(ttk.Label(pills, text="ยังไม่มีปุ่มคำถาม พิมพ์คำถามแล้วกด '+ บันทึกเป็นปุ่ม'", font=small_font, foreground="#777"))
        qa_hint.config(text="โหมดแก้ไข: คลิกปุ่มเพื่อลบ" if qa["edit"] else "คลิกปุ่มคำถามเพื่อถามทันที · ถามต่อเนื่องได้")

    def add_question(text):
        text = (text or "").strip()
        if not text:
            set_status("พิมพ์คำถามในช่องก่อน แล้วกด '+ บันทึกเป็นปุ่ม'"); return
        if text in settings["questions"]:
            set_status("มีปุ่มคำถามนี้อยู่แล้ว"); return
        settings["questions"].append(text); save_settings(); render_question_pills()
        set_status(f"เพิ่มปุ่มคำถาม: {text}")

    def delete_question(i):
        if 0 <= i < len(settings["questions"]):
            removed = settings["questions"].pop(i); save_settings(); render_question_pills()
            set_status(f"ลบปุ่มคำถาม: {removed}")

    def toggle_qa_edit():
        qa["edit"] = not qa["edit"]
        qa_edit_btn.config(text="เสร็จ" if qa["edit"] else "แก้ไขปุ่ม")
        render_question_pills()

    def toggle_qa(force=None):
        want = (not qa["open"]) if force is None else force
        qa["open"] = want
        if want:
            qa_frame.pack(fill="x", padx=10, pady=(0, 4))   # ใต้แถวปุ่มในกล่องล่าง (จองที่ก่อนช่องข้อความ)
            qa_btn.config(text="❓ ถามโมเดล ▴")
            render_question_pills()
            sh = root.winfo_screenheight()
            if root.winfo_height() < 900 and sh >= 1000:
                root.geometry(f"{max(root.winfo_width(), 1000)}x{min(980, sh - 80)}")
            qa_inp.focus_set()
        else:
            qa_frame.pack_forget(); qa_btn.config(text="❓ ถามโมเดล ▾")
        settings["qaOpen"] = want; save_settings()

    def qa_set_busy(busy):
        qa["busy"] = busy
        qa_ask_btn.state(["disabled"] if busy else ["!disabled"])
        for b in pill_widgets:
            try:
                b.state(["disabled"] if busy else ["!disabled"])
            except Exception:
                pass

    def qa_reset():
        qa["history"].clear()

    def ask_question(question):
        question = (question or "").strip()
        if not question:
            set_status("พิมพ์คำถาม หรือคลิกปุ่มคำถาม"); return
        if qa["busy"]:
            set_status("กำลังตอบคำถามก่อนหน้าอยู่ กด 'หยุด' ก่อนถ้าต้องการถามใหม่"); return
        if worker["busy"]:
            set_status("รอให้แปลเสร็จก่อน แล้วค่อยถาม"); return
        if not st["model"]:
            set_status("ยังไม่ได้เชื่อมต่อโมเดล"); return
        src_text = src.get("1.0", "end").strip()
        translation = dst.get("1.0", "end").strip()
        if not src_text and not translation:
            set_status("กรุณาใส่ข้อความหรือแปลก่อน"); return
        s_lang = detect_lang(src_text) if src_text else ("en" if detect_lang(translation) == "th" else "th")
        d_lang = "en" if s_lang == "th" else "th"
        msgs = build_qa_messages(src_text, s_lang, translation, d_lang, qa["history"], question)
        if not qa["open"]:
            toggle_qa(True)
        qa["question"] = question
        qa_out.delete("1.0", "end")
        qa["stop"].clear(); qa_set_busy(True); stop_speech()
        set_status(f"กำลังถาม: {question[:60]} ...")

        def job():
            t0 = time.time(); buf = []; stats = {}
            try:
                gen = chat_stream(st["model"], msgs, 0.4, qa["stop"])
                while True:
                    try:
                        piece = next(gen)
                    except StopIteration as e:
                        stats = e.value or {}; break
                    buf.append(piece); q.put(("qa_piece", piece))
                q.put(("qa_done", "".join(buf), stats, time.time() - t0))
            except Exception as e:
                q.put(("qa_error", str(e)))
        threading.Thread(target=job, daemon=True).start()

    def qa_finish(answer, stats, elapsed):
        qa_set_busy(False)
        answer = clean_output(answer)
        qa_out.delete("1.0", "end"); qa_out.insert("1.0", answer)
        stopped = qa["stop"].is_set()
        if answer and not stopped:
            qa["history"].append((qa["question"], answer))
        ev, ed = stats.get("eval_count") or 0, stats.get("eval_duration") or 0
        speed = f" · {ev/(ed/1e9):.1f} tok/s" if ed else ""
        set_status(("หยุดตอบแล้ว" if stopped else "ตอบเสร็จ") + f" · {elapsed:.1f} วินาที{speed} · ถามต่อได้ ({len(qa['history'])} คำถาม)")
        if os.environ.get("TRANSLATOR_QA_DEMO"):
            print(f"[qa-demo] ตอบเสร็จ {elapsed:.1f}s{speed}\n{answer}", file=sys.stderr, flush=True)
        if answer and not stopped and qa_speak_var.get():
            speak_text(answer)

    qa_inp.bind("<Return>", lambda e: (ask_question(qa_inp.get()), "break"))
    # ==================== จบบล็อก Q&A ====================

    # ---------- actions
    def current_direction(text):
        d = settings["direction"]
        if d == "th2en":
            return "th", "en"
        if d == "en2th":
            return "en", "th"
        s = detect_lang(text)
        return s, ("en" if s == "th" else "th")

    def start_translate(variant=False, text=None):
        if worker["busy"]:
            return
        if text is None:
            text = src.get("1.0", "end").strip()
        if not text:
            set_status("กรุณาใส่ข้อความก่อน"); return
        if not st["model"]:
            set_status("ยังไม่ได้เชื่อมต่อโมเดล - กด ⚙ ผู้ให้บริการ เพื่อดาวน์โหลดโมเดล หรือกด F5 แล้วลองใหม่"); return
        s, d = current_direction(text)
        level = level_var.get()
        hits = glossary_for(text, s, level, glossary)
        msgs = build_messages(text, s, d, level, hits, variant)
        src_lbl.set(f"ข้อความต้นทาง ({LANGS[s]})"); dst_lbl.set(f"คำแปล ({LANGS[d]})")
        dst.delete("1.0", "end")
        stop_speech()
        qa_reset()                     # ข้อความใหม่ -> ล้างบทสนทนาถาม-ตอบเดิม
        if autospeak_var.get():
            stream_speak_begin(d)      # อ่านประโยคแรกทันทีที่แปลเสร็จ ไม่ต้องรอทั้งหมด
        last_src["text"] = text        # จำข้อความที่กำลังแปล ถ้าต้นทางเปลี่ยนไปจากนี้จะล้างกล่องแปล/คำตอบ
        qa_out.delete("1.0", "end")
        worker["stop"].clear(); worker["busy"] = True
        translate_btn.state(["disabled"]); stop_btn.state(["!disabled"])
        set_status(f"กำลังแปล {LANGS[s]} → {LANGS[d]} · {LEVELS[level]['label']}" + (f" · glossary {len(hits)} คำ" if hits else "") + " ...")
        temp = LEVELS[level]["temp"] + (0.35 if variant else 0)

        def job():
            t0 = time.time(); buf = []; stats = {}
            try:
                gen = chat_stream(st["model"], msgs, temp, worker["stop"])
                while True:
                    try:
                        piece = next(gen)
                    except StopIteration as e:
                        stats = e.value or {}; break
                    buf.append(piece); q.put(("piece", piece))
                q.put(("done", "".join(buf), stats, time.time() - t0, text, level))
            except Exception as e:
                q.put(("error", str(e)))
        worker["thread"] = threading.Thread(target=job, daemon=True); worker["thread"].start()

    def finish(result, stats, elapsed, text, level):
        result = clean_output(result)
        dst.delete("1.0", "end"); dst.insert("1.0", result)
        st["last_result"] = result
        if result and not worker["stop"].is_set():
            history.append({"ts": time.strftime("%Y-%m-%d %H:%M"), "level": level, "src": text, "dst": result})
            save_history()
            if hist_shown["on"]:
                refresh_history()
        ev, ed = stats.get("eval_count") or 0, stats.get("eval_duration") or 0
        speed = f" · {ev/(ed/1e9):.1f} tok/s" if ed else ""
        set_status(("หยุดแล้ว" if worker["stop"].is_set() else "แปลเสร็จ") + f" · {elapsed:.1f} วินาที{speed} · {st['model']}")
        if st.get("demo_t0"):
            print(f"[demo] {time.time() - st['demo_t0']:5.1f}s  แปลเสร็จ ({elapsed:.1f}s{speed})", file=sys.stderr, flush=True)
        qa_demo = os.environ.get("TRANSLATOR_QA_DEMO")
        if qa_demo and not st.get("qa_demo_done"):   # สำหรับทดสอบ: ถามคำถามนี้ทันทีหลังแปลเสร็จ
            st["qa_demo_done"] = True
            root.after(500, lambda: ask_question(qa_demo))
        if worker["stop"].is_set():
            stop_speech()
        else:
            stream_speak_end(result)

    # ---------- เสียงอ่าน: แบ่งท่อน สร้างขนาน เล่นทันทีที่ท่อนแรกเสร็จ (เสียงเก่าถูกหยุดก่อนเสมอ ไม่ซ้อนกัน)
    replacements = load_replacements()

    def cleanup_tts_tmp():
        """ลบไฟล์เสียงชั่วคราวที่เก่ากว่า 1 วัน"""
        try:
            cutoff = time.time() - 86400
            for f in os.listdir(TTS_TMP):
                p = os.path.join(TTS_TMP, f)
                if os.path.isfile(p) and os.path.getmtime(p) < cutoff:
                    os.remove(p)
        except Exception:
            pass
    threading.Thread(target=cleanup_tts_tmp, daemon=True).start()
    pipeline = TtsPipeline(lambda kind, msg: q.put(("tts_event", kind, msg)))

    speak = {"on": False, "buf": "", "lang": "th"}   # สถานะการอ่านแบบสตรีมระหว่างแปล

    def speech_config(lang):
        """เลือกเสียงตามภาษาของข้อความ (edge-tts ไม่ส่งเสียงถ้าเสียงกับภาษาไม่ตรงกัน) คืน (voice, rate, clone_id, ชื่อที่แสดง)"""
        name = tts_voice_var.get()
        clone_id = clone_ids.get(name)
        base_voice = TTS_VOICES.get(name, ("th-TH-PremwadeeNeural", "th"))[0] if not clone_id else "th-TH-NiwatNeural"
        voice = base_voice if lang == "th" else EN_VOICES.get(base_voice, "en-US-JennyNeural")
        return voice, TTS_RATES.get(tts_rate_var.get(), "+0%"), (clone_id if lang == "th" else None), name

    def feed_sentence(text, lang):
        text = clean_for_tts(text)
        if not text:
            return
        if lang == "th":
            text = apply_replacements(text, replacements)
        pipeline.feed(text)

    def speak_text(text):
        """ปุ่ม 🔊: อ่านทั้งข้อความ แบ่งเป็นประโยค เริ่มเล่นทันทีที่ประโยคแรกเสร็จ"""
        text = clean_for_tts(text or "")
        if not text:
            return
        stop_speech()
        lang = detect_lang(text)
        voice, rate, clone_id, name = speech_config(lang)
        pipeline.begin(voice, rate, clone_id)
        # เสียงโคลนใช้เวลาต่อครั้งนานมาก จึงส่งทั้งก้อนเดียว ส่วนเสียงปกติแบ่งประโยคเพื่อให้เริ่มได้เร็ว
        chunks = [text] if clone_id else split_tts_chunks(text)
        set_status(f"กำลังสร้างเสียง ({name}{' · โคลน' if clone_id else ''}) {len(chunks)} ท่อน ...")
        for c in chunks:
            feed_sentence(c, lang)
        pipeline.finish()

    def stream_speak_begin(lang):
        """เริ่มอ่านตั้งแต่ประโยคแรกที่แปลเสร็จ (เรียกตอนเริ่มแปล เมื่อเปิด 'อ่านอัตโนมัติ')"""
        voice, rate, clone_id, name = speech_config(lang)
        pipeline.begin(voice, rate, clone_id)
        speak.update(on=True, buf="", lang=lang, clone=bool(clone_id))

    def stream_speak_piece(piece):
        if not speak["on"]:
            return
        speak["buf"] += piece
        if speak["clone"]:
            return                                   # โคลน: รอจบแล้วอ่านทีเดียว
        sents, speak["buf"] = pop_sentences(speak["buf"])
        for s in sents:
            feed_sentence(s, speak["lang"])

    def stream_speak_end(full_text):
        if not speak["on"]:
            return
        speak["on"] = False
        if speak["clone"]:
            feed_sentence(clean_output(full_text), speak["lang"])
        else:
            sents, _ = pop_sentences(speak["buf"], final=True)
            for s in sents:
                feed_sentence(s, speak["lang"])
        speak["buf"] = ""
        pipeline.finish()

    def stop_speech():
        speak["on"] = False; speak["buf"] = ""
        pipeline.stop()

    def on_tts_event(kind, msg):
        if st.get("demo_t0"):
            print(f"[demo] {time.time() - st['demo_t0']:5.1f}s  {kind}: {msg}", file=sys.stderr, flush=True)
        if kind == "status":
            set_status(msg)
        elif kind == "done":
            set_status(msg)
        elif kind == "error":
            set_status("เสียงอ่านไม่สำเร็จ: " + msg[:140])

    # ---------- ไอคอนลอยเมื่อเลือกข้อความ: พื้นโปร่งใส เด้งขึ้นลง เปลี่ยนสีวน
    FLOAT_KEY = "#010203"          # สีคีย์ที่ Windows ทำให้โปร่งใส
    FLOAT_SIZE, FLOAT_FRAMES = 56, 16
    frames = build_float_frames(FLOAT_SIZE, FLOAT_FRAMES, FLOAT_KEY)
    if not frames:
        try:
            frames = [tk.PhotoImage(file=os.path.join(BASE, "translator.png")).subsample(5)]
        except Exception:
            frames = []
    flt = tk.Toplevel(root); flt.title("translator-float-icon"); flt.overrideredirect(True); flt.attributes("-topmost", True); flt.withdraw()
    flt.configure(background=FLOAT_KEY)
    try:
        flt.attributes("-transparentcolor", FLOAT_KEY)
    except Exception:
        pass
    flt_btn = tk.Label(flt, image=frames[0] if frames else None, text="" if frames else "แปล", background=FLOAT_KEY,
                       foreground="#56E0D8", cursor="hand2", borderwidth=0, padx=0, pady=0, font=(fam, 10, "bold"))
    flt_btn.pack()
    flt_state = {"hwnd": None, "timer": None, "shown_at": 0, "anim": None, "x": 0, "y": 0, "tick": 0}

    def animate_float():
        if flt.state() == "withdrawn":
            flt_state["anim"] = None; return
        t = flt_state["tick"] = flt_state["tick"] + 1
        if frames:
            flt_btn.configure(image=frames[t % len(frames)])          # เปลี่ยนสีวน
        bounce = int(abs(math.sin(t / 5.0)) * 10)                        # เด้งขึ้นลง 10 px
        flt.geometry(f"+{flt_state['x']}+{flt_state['y'] - bounce}")
        flt_state["anim"] = root.after(70, animate_float)

    def float_hwnd():
        if flt_state["hwnd"] is None:
            try:
                flt_state["hwnd"] = make_noactivate(flt.winfo_id())
            except Exception:
                flt_state["hwnd"] = 0
        return flt_state["hwnd"]

    def show_float(x, y):
        if not float_var.get() or worker["busy"]:
            return
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w = h = FLOAT_SIZE
        px, py = min(x + 14, sw - w - 4), min(y + 18, sh - h - 4)
        flt_state["x"], flt_state["y"] = px, py
        flt.geometry(f"+{px}+{py}"); flt.deiconify(); flt.lift(); flt.attributes("-topmost", True)
        float_hwnd()
        flt_state["shown_at"] = time.time()
        if flt_state["timer"]:
            root.after_cancel(flt_state["timer"])
        flt_state["timer"] = root.after(5000, hide_float)
        if not flt_state["anim"]:
            animate_float()

    def hide_float():
        if flt_state["timer"]:
            root.after_cancel(flt_state["timer"]); flt_state["timer"] = None
        if flt_state["anim"]:
            root.after_cancel(flt_state["anim"]); flt_state["anim"] = None
        flt.withdraw()

    def float_clicked(_=None):
        hide_float()
        threading.Thread(target=lambda: (send_ctrl_c(), time.sleep(0.25), q.put(("hotkey",))), daemon=True).start()
    flt_btn.bind("<Button-1>", float_clicked)

    def is_own_window(fg_hwnd, x, y):
        """คลิกในหน้าต่างโปรแกรมเราหรือบนไอคอนลอย ไม่ต้องแสดงไอคอน"""
        try:
            user32 = ctypes.windll.user32
            ours = user32.GetAncestor(root.winfo_id(), GA_ROOT)
            if fg_hwnd == ours:
                return True
            if flt.state() != "withdrawn":
                fx, fy = flt.winfo_rootx(), flt.winfo_rooty()
                if fx - 2 <= x <= fx + flt.winfo_width() + 2 and fy - 2 <= y <= fy + flt.winfo_height() + 2:
                    return True
        except Exception:
            pass
        return False


    def pump():
        try:
            while True:
                item = q.get_nowait()
                kind = item[0]
                if kind == "piece":
                    dst.insert("end", item[1]); dst.see("end")
                    if item[1]:
                        stream_speak_piece(item[1])
                elif kind == "done":
                    worker["busy"] = False; translate_btn.state(["!disabled"])
                    finish(*item[1:])
                elif kind == "error":
                    worker["busy"] = False; translate_btn.state(["!disabled"])
                    stop_speech(); set_status("ผิดพลาด: " + item[1][:200])
                elif kind == "models":
                    on_models(item[1])
                elif kind == "hotkey":
                    hotkey_captured()
                elif kind == "select":
                    show_float(item[1], item[2])
                elif kind == "hide_float":
                    if flt.state() != "withdrawn" and time.time() - flt_state["shown_at"] > 0.3:
                        hide_float()
                elif kind == "tts_event":
                    on_tts_event(item[1], item[2])
                elif kind == "qa_piece":
                    qa_out.insert("end", item[1]); qa_out.see("end")
                elif kind == "qa_done":
                    qa_finish(item[1], item[2], item[3])
                elif kind == "qa_error":
                    qa_set_busy(False); set_status("ถามไม่สำเร็จ: " + item[1][:200])
        except queue.Empty:
            pass
        root.after(60, pump)

    def swap():
        a = src.get("1.0", "end").strip(); b = dst.get("1.0", "end").strip()
        src.delete("1.0", "end"); dst.delete("1.0", "end")
        src.insert("1.0", b); dst.insert("1.0", a)

    def copy_result():
        r = dst.get("1.0", "end").strip()
        if r:
            root.clipboard_clear(); root.clipboard_append(r); st["last_clip"] = r
            set_status("คัดลอกคำแปลแล้ว")

    def read_clipboard():
        try:
            return root.clipboard_get()
        except Exception:
            return ""

    def paste_and_translate():
        t = read_clipboard().strip()
        if t:
            src.delete("1.0", "end"); src.insert("1.0", t); start_translate()

    def bring_to_front():
        root.deiconify(); root.lift(); root.attributes("-topmost", True)
        root.after(300, lambda: root.attributes("-topmost", topmost_var.get())); root.focus_force()

    def hotkey_captured():
        t = read_clipboard().strip()
        if t and t != st["last_result"]:
            src.delete("1.0", "end"); src.insert("1.0", t)
            bring_to_front(); start_translate()
        else:
            bring_to_front(); set_status("ไม่พบข้อความที่เลือก - ลากคลุมข้อความก่อนแล้วกด " + HOTKEY_LABEL)

    def on_hotkey():           # เรียกจากเธรด hotkey
        send_ctrl_c(); time.sleep(0.25); q.put(("hotkey",))

    def hotkey_status(hot_ok, hook_ok):
        st["hotkey_ok"] = hot_ok
        parts = []
        parts.append("ลากคลุมข้อความในโปรแกรมใดก็ได้ แล้วคลิกไอคอนหุ่นยนต์ที่ลอยขึ้นมา" if hook_ok else "ตรวจการลากคลุมไม่ได้")
        parts.append(f"หรือกด {hot_ok}" if hot_ok else "คีย์ลัด Ctrl+Alt+T/Y ถูกโปรแกรมอื่นใช้อยู่")
        hotkey_var.set(" · ".join(parts))

    def clip_poll():
        if clip_var.get() and not worker["busy"]:
            t = read_clipboard()
            if t and t.strip() and t != st["last_clip"] and t.strip() != st["last_result"]:
                st["last_clip"] = t
                src.delete("1.0", "end"); src.insert("1.0", t.strip()); start_translate()
            elif st["last_clip"] is None:
                st["last_clip"] = t
        root.after(700, clip_poll)

    def on_models(models):
        """models = รายการโมเดลในเครื่อง (None = ไม่พบ Ollama) -> เลือกเส้นทางตามโหมดใน ⚙ ผู้ให้บริการ"""
        a = settings.get("api") or {}
        mode = a.get("mode", "auto")
        local_ok = bool(models)
        api_ok = api_configured()
        api_entry = (API_TAG + a.get("model", "")) if api_ok else None
        values = list(models or []) + ([api_entry] if api_entry else [])
        st["models"] = list(models or []); model_cb["values"] = values
        want_api = (mode == "api" and api_ok) or (mode == "auto" and not local_ok and api_ok)
        if want_api:
            use_backend("api"); model_var.set(api_entry)
            why = "" if mode == "api" else " (ไม่พบโมเดลในเครื่อง จึงสลับให้อัตโนมัติ)"
            set_status(f"พร้อมใช้งาน · โมเดลออนไลน์ {a.get('model')} ผ่าน API{why}")
        elif local_ok:
            use_backend("local")
            saved = settings.get("model", "")
            chosen = saved if saved in models else pick_model(models)
            model_var.set(chosen); st["model"] = chosen
            note = "" if chosen.startswith("scb10x/typhoon2.5") else " (แนะนำ typhoon2.5-qwen3-4b สำหรับภาษาไทย)"
            set_status(f"พร้อม · โมเดล {chosen}{note} · กำลังอุ่นเครื่องเข้า GPU ...")
            threading.Thread(target=lambda: (warm_up(chosen), q.put(("piece", ""))), daemon=True).start()
            root.after(1500, lambda: set_status(f"พร้อมใช้งาน · {chosen}") if not worker["busy"] else None)
        else:
            use_backend("local"); st["model"] = ""
            model_var.set("ไม่พบโมเดล" if models is None else "ยังไม่มีโมเดลในเครื่อง")
            set_status(("เชื่อมต่อ Ollama ไม่ได้" if models is None else "Ollama ทำงานแต่ยังไม่มีโมเดล")
                       + " - กด ⚙ ผู้ให้บริการ เพื่อดาวน์โหลดโมเดลในเครื่อง หรือใส่ API key ใช้โมเดลออนไลน์")
            return
        demo_text = os.environ.get("TRANSLATOR_SPEAK_DEMO")
        if demo_text and not st.get("demo_started"):   # สำหรับทดสอบ: แปล + อ่านอัตโนมัติด้วยเสียงที่ระบุ
            st["demo_started"] = True
            voice_pick = os.environ.get("TRANSLATOR_SPEAK_VOICE")

            def demo():
                if voice_pick and voice_pick in voice_names:
                    tts_voice_var.set(voice_pick); autospeak_var.set(True)   # ระบุเสียง = ทดสอบอ่านอัตโนมัติด้วย
                src.delete("1.0", "end"); src.insert("1.0", demo_text)
                st["demo_t0"] = time.time(); print("[demo] เริ่มแปล", file=sys.stderr, flush=True)
                start_translate()
            root.after(4000, demo)

    def connect():
        set_status("กำลังเชื่อมต่อ Ollama (ถ้ายังไม่เปิดจะเปิดให้เอง) ...")
        threading.Thread(target=lambda: q.put(("models", ensure_ollama())), daemon=True).start()

    # ---------- ⚙ ผู้ให้บริการ: ตั้งค่า API ออนไลน์สำรอง (ใช้เมื่อเครื่องไม่มีโมเดลในเครื่อง หรือเลือกใช้เอง)
    def open_provider_dialog():
        import webbrowser
        a = dict(settings.get("api") or {})
        dlg = tk.Toplevel(root); dlg.title("ผู้ให้บริการโมเดล"); dlg.transient(root); dlg.grab_set(); dlg.resizable(False, False)
        body = ttk.Frame(dlg, padding=14); body.pack(fill="both", expand=True)
        ttk.Label(body, text="เส้นทางที่ใช้แปล", font=(fam, 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        mode_var = tk.StringVar(value=a.get("mode", "auto"))
        mf = ttk.Frame(body); mf.grid(row=1, column=0, columnspan=3, sticky="w")
        for val, txt in (("auto", "อัตโนมัติ: ใช้โมเดลในเครื่อง ถ้าไม่มีให้ใช้ API"), ("local", "ในเครื่องเท่านั้น (Ollama)"), ("api", "API ออนไลน์เท่านั้น")):
            ttk.Radiobutton(mf, text=txt, value=val, variable=mode_var).pack(anchor="w")
        ttk.Separator(body).grid(row=2, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(body, text="ผู้ให้บริการ (API รูปแบบ OpenAI)", font=(fam, 10, "bold")).grid(row=3, column=0, sticky="w", pady=(0, 4))
        preset_var = tk.StringVar(value=a.get("preset") if a.get("preset") in API_PRESETS else list(API_PRESETS)[0])
        preset_cb = ttk.Combobox(body, textvariable=preset_var, values=list(API_PRESETS), state="readonly", width=52)
        preset_cb.grid(row=4, column=0, columnspan=3, sticky="w")
        note_var = tk.StringVar(); ttk.Label(body, textvariable=note_var, font=small_font, foreground="#555", wraplength=520, justify="left").grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 6))
        ttk.Label(body, text="Base URL:").grid(row=6, column=0, sticky="w")
        base_var = tk.StringVar(value=a.get("base", "")); ttk.Entry(body, textvariable=base_var, width=52).grid(row=6, column=1, columnspan=2, sticky="w", pady=2)
        ttk.Label(body, text="API key:").grid(row=7, column=0, sticky="w")
        key_var = tk.StringVar(value=a.get("key", "")); key_ent = ttk.Entry(body, textvariable=key_var, width=52, show="•"); key_ent.grid(row=7, column=1, columnspan=2, sticky="w", pady=2)
        show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(body, text="แสดงคีย์", variable=show_var, command=lambda: key_ent.config(show="" if show_var.get() else "•")).grid(row=8, column=1, sticky="w")
        link = ttk.Label(body, text="", foreground="#1a5fb4", cursor="hand2", font=small_font); link.grid(row=8, column=2, sticky="w")
        ttk.Label(body, text="โมเดล:").grid(row=9, column=0, sticky="w")
        model_v = tk.StringVar(value=a.get("model", ""))
        mcb = ttk.Combobox(body, textvariable=model_v, width=40); mcb.grid(row=9, column=1, sticky="w", pady=2)
        msg_var = tk.StringVar(); ttk.Label(body, textvariable=msg_var, font=small_font, foreground="#0E6B5B", wraplength=520, justify="left").grid(row=11, column=0, columnspan=3, sticky="w", pady=(6, 0))

        def apply_preset(_=None):
            p = API_PRESETS[preset_var.get()]
            if p["base"]:
                base_var.set(p["base"])
            mcb["values"] = p["models"]
            if p["models"] and (not model_v.get() or model_v.get() not in p["models"] and a.get("preset") != preset_var.get()):
                model_v.set(p["models"][0])
            note_var.set(p["note"])
            link.config(text=("สมัคร/ขอคีย์: " + p["signup"]) if p["signup"] else "")
            link.bind("<Button-1>", lambda e, u=p["signup"]: webbrowser.open(u) if u else None)
        preset_cb.bind("<<ComboboxSelected>>", apply_preset); apply_preset()

        def load_models():
            if not (base_var.get().strip() and key_var.get().strip()):
                msg_var.set("ใส่ Base URL และ API key ก่อน"); return
            msg_var.set("กำลังโหลดรายการโมเดล ...")

            def job():
                try:
                    ids = list_models_openai(base_var.get().strip(), key_var.get().strip())
                    dlg.after(0, lambda: (mcb.configure(values=ids), msg_var.set(f"โหลดได้ {len(ids)} โมเดล เลือกจากรายการได้")))
                except Exception as e:
                    dlg.after(0, lambda: msg_var.set("โหลดรายการไม่ได้: " + str(e)[:160]))
            threading.Thread(target=job, daemon=True).start()
        ttk.Button(body, text="โหลดรายการโมเดล", command=load_models).grid(row=9, column=2, sticky="w", padx=(6, 0))

        def test_api():
            b, k, m = base_var.get().strip(), key_var.get().strip(), model_v.get().strip()
            if not (b and k and m):
                msg_var.set("ใส่ Base URL, API key และโมเดลให้ครบก่อน"); return
            msg_var.set("กำลังทดสอบ ...")

            def job():
                try:
                    t0 = time.time()
                    out = "".join(stream_chat_openai(b, k, m, [{"role": "user", "content": "แปลเป็นอังกฤษ: สวัสดี ตอบเฉพาะคำแปล"}], 0.2))
                    dlg.after(0, lambda: msg_var.set(f"สำเร็จใน {time.time()-t0:.1f} วินาที · ตอบว่า: {clean_output(out)[:80]}"))
                except Exception as e:
                    dlg.after(0, lambda: msg_var.set("ทดสอบไม่ผ่าน: " + str(e)[:200]))
            threading.Thread(target=job, daemon=True).start()

        def save():
            settings["api"] = {"mode": mode_var.get(), "preset": preset_var.get(), "base": base_var.get().strip(),
                               "key": key_var.get().strip(), "model": model_v.get().strip()}
            save_settings(); dlg.destroy(); connect()
        # ---- โมเดลในเครื่อง: ดาวน์โหลดผ่าน Ollama จากในแอป (สำหรับเครื่องที่ติดตั้งแล้วยังไม่มีโมเดล)
        ttk.Separator(body).grid(row=14, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(body, text="โมเดลในเครื่อง (Ollama)", font=(fam, 10, "bold")).grid(row=15, column=0, sticky="w", pady=(0, 4))
        local_info = tk.StringVar()
        ttk.Label(body, textvariable=local_info, font=small_font, foreground="#555", wraplength=520, justify="left").grid(row=16, column=0, columnspan=3, sticky="w")
        ttk.Label(body, text="ชื่อโมเดล:").grid(row=17, column=0, sticky="w")
        pull_v = tk.StringVar(value=DEFAULT_MODEL)
        pull_cb = ttk.Combobox(body, textvariable=pull_v, width=40, values=[DEFAULT_MODEL, "scb10x/llama3.2-typhoon2-3b-instruct", "maternion/spark-x2.5:4b-q4_K_M", "qwen2.5:7b-instruct"])
        pull_cb.grid(row=17, column=1, sticky="w", pady=2)
        pull_btn = ttk.Button(body, text="ดาวน์โหลด/ติดตั้ง"); pull_btn.grid(row=17, column=2, sticky="w", padx=(6, 0))
        pull_msg = tk.StringVar(); ttk.Label(body, textvariable=pull_msg, font=small_font, foreground="#0E6B5B", wraplength=520, justify="left").grid(row=18, column=0, columnspan=3, sticky="w", pady=(4, 0))

        def refresh_local_info():
            exe = find_ollama_exe(); ms = list_models()
            if ms is None:
                local_info.set(("พบ Ollama ที่ " + exe + " แต่เซิร์ฟเวอร์ยังไม่ทำงาน (กด F5 ในหน้าหลักเพื่อให้โปรแกรมเปิดให้)") if exe
                               else "ไม่พบ Ollama ในเครื่อง: ติดตั้งจาก https://ollama.com/download/windows หรือรัน Install-LocalTranslator.bat แล้วกลับมากดดาวน์โหลดที่นี่")
            else:
                local_info.set(f"Ollama ทำงานอยู่ · มีโมเดลในเครื่อง {len(ms)} ตัว" + (": " + ", ".join(ms[:4]) + (" ..." if len(ms) > 4 else "") if ms else " (ยังไม่มี) กดดาวน์โหลดด้านล่าง ~2.5 GB ต้องต่ออินเทอร์เน็ต"))
        refresh_local_info()

        def do_pull():
            name = pull_v.get().strip()
            if not name:
                return
            if list_models() is None:
                pull_msg.set("Ollama ยังไม่ทำงาน กด F5 ในหน้าหลักก่อน หรือติดตั้ง Ollama"); return
            pull_btn.state(["disabled"]); pull_msg.set(f"กำลังดาวน์โหลด {name} ...")

            def prog(status, pct, done, tot):
                txt = f"{status}" + (f" {pct}% ({done/1e9:.2f}/{tot/1e9:.2f} GB)" if pct is not None else "")
                dlg.after(0, lambda: pull_msg.set(txt))

            def job():
                try:
                    pull_model(name, prog)
                    dlg.after(0, lambda: (pull_msg.set(f"ติดตั้ง {name} เสร็จแล้ว โปรแกรมจะเชื่อมต่อใหม่"), refresh_local_info(), pull_btn.state(["!disabled"]), connect()))
                except Exception as e:
                    dlg.after(0, lambda: (pull_msg.set("ดาวน์โหลดไม่สำเร็จ: " + str(e)[:200]), pull_btn.state(["!disabled"])))
            threading.Thread(target=job, daemon=True).start()
        pull_btn.config(command=do_pull)

        bf = ttk.Frame(body); bf.grid(row=12, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(bf, text="ทดสอบการเชื่อมต่อ", command=test_api).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="บันทึกและใช้งาน", style="Big.TButton", command=save).pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="ยกเลิก", command=dlg.destroy).pack(side="left")
        ttk.Label(body, text="คีย์ถูกเก็บใน settings.json ข้างโปรแกรม (ไม่ส่งไปที่อื่นนอกจากผู้ให้บริการที่เลือก)", font=small_font, foreground="#777").grid(row=13, column=0, columnspan=3, sticky="w", pady=(8, 0))
        bf.grid_configure(row=19)   # แถวปุ่มบันทึกอยู่ล่างสุด ใต้ส่วนโมเดลในเครื่อง
        dlg.update_idletasks()
        dlg.geometry(f"+{root.winfo_rootx() + 80}+{root.winfo_rooty() + 80}")

    # ---------- คีย์ลัดแก้ไขข้อความที่ใช้ได้ทุกภาษาแป้นพิมพ์ + เมนูคลิกขวา
    # Tk ผูก Ctrl+V/C/X/A กับ "ตัวอักษร" v/c/x/a เมื่อแป้นพิมพ์อยู่ที่ภาษาไทย keysym เป็นอักษรไทย จึงวาง/คัดลอกไม่ได้
    # แก้โดยดูรหัสปุ่มจริง (keycode 86=V 67=C 88=X 65=A) เฉพาะกรณีที่ keysym ไม่ใช่อักษรละติน (ภาษาอังกฤษปล่อยให้ Tk จัดการเอง)
    EDIT_KEYS = {86: "<<Paste>>", 67: "<<Copy>>", 88: "<<Cut>>", 65: "<<SelectAll>>"}

    def ctrl_edit(event):
        w = event.widget
        if event.keysym.lower() in ("v", "c", "x", "a") or event.keycode not in EDIT_KEYS:
            return
        if not isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            return
        action = EDIT_KEYS[event.keycode]
        if action == "<<SelectAll>>":
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end")
            else:
                w.select_range(0, "end"); w.icursor("end")
        else:
            w.event_generate(action)
        return "break"
    root.bind_all("<Control-KeyPress>", ctrl_edit, add="+")

    edit_menu = tk.Menu(root, tearoff=0)
    edit_target = {"w": None}

    def menu_do(action):
        w = edit_target["w"]
        if w is None:
            return
        if action == "selectall":
            if isinstance(w, tk.Text):
                w.tag_add("sel", "1.0", "end")
            else:
                w.select_range(0, "end"); w.icursor("end")
        else:
            w.event_generate({"paste": "<<Paste>>", "copy": "<<Copy>>", "cut": "<<Cut>>"}[action])
    for label, act in (("วาง", "paste"), ("คัดลอก", "copy"), ("ตัด", "cut"), ("เลือกทั้งหมด", "selectall")):
        edit_menu.add_command(label=label, command=lambda a=act: menu_do(a))

    def show_edit_menu(event):
        w = event.widget
        if isinstance(w, (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox)):
            edit_target["w"] = w; w.focus_set()
            try:
                edit_menu.tk_popup(event.x_root, event.y_root)
            finally:
                edit_menu.grab_release()
            return "break"
    root.bind_all("<Button-3>", show_edit_menu, add="+")

    # ---------- bindings
    root.bind("<Control-Return>", lambda e: (start_translate(), "break"))
    src.bind("<Control-Return>", lambda e: (start_translate(), "break"))

    last_src = {"text": None}

    def on_src_modified(_=None):
        """ข้อความต้นทางเปลี่ยน (พิมพ์ วาง ไอคอนลอย คีย์ลัด) -> ล้างกล่องคำแปลและกล่องคำตอบของโมเดลทุกครั้ง"""
        if not src.edit_modified():
            return
        src.edit_modified(False)
        if worker["busy"]:
            return
        cur = src.get("1.0", "end").strip()
        if last_src["text"] is not None and cur != last_src["text"]:
            last_src["text"] = None
            dst.delete("1.0", "end"); qa_out.delete("1.0", "end"); qa_reset()
            stop_speech()
    src.bind("<<Modified>>", on_src_modified)
    root.bind("<Escape>", lambda e: worker["stop"].set())
    root.bind("<F5>", lambda e: connect())
    src.bind("<Control-a>", lambda e: (src.tag_add("sel", "1.0", "end"), "break"))
    dst.bind("<Control-a>", lambda e: (dst.tag_add("sel", "1.0", "end"), "break"))
    root.protocol("WM_DELETE_WINDOW", lambda: (worker["stop"].set(), stop_speech(), save_settings(), root.destroy()))

    apply_topmost()
    connect()
    threading.Thread(target=win_event_thread, daemon=True,
                     args=(on_hotkey, lambda x, y: q.put(("select", x, y)), lambda: q.put(("hide_float",)),
                           is_own_window, hotkey_status)).start()
    root.after(60, pump)
    root.after(1000, clip_poll)
    src.focus_set()
    root.after(300, lambda: pane.sashpos(0, root.winfo_width() // 2 - 10))  # แบ่งสองช่องเท่ากัน
    if settings.get("qaOpen"):
        root.after(400, lambda: toggle_qa(True))
    if os.environ.get("TRANSLATOR_PROVIDER_DEMO"):   # สำหรับทดสอบ: เปิดหน้าต่างตั้งค่าผู้ให้บริการ
        root.after(2500, open_provider_dialog)
    if os.environ.get("TRANSLATOR_FLOAT_DEMO"):  # สำหรับทดสอบ: โชว์ไอคอนลอยกลางจอซ้ำทุก 4 วินาที
        print("float frames:", len(frames), file=sys.stderr)

        def demo():
            show_float(root.winfo_screenwidth() // 2, root.winfo_screenheight() // 2); root.after(4000, demo)
        root.after(1500, demo)
    if minimized:
        root.iconify()
    root.mainloop()


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Local Translator (Ollama)")
    ap.add_argument("--cli", action="store_true", help="แปลใน console แทนหน้าต่าง")
    ap.add_argument("--level", choices=LEVEL_ORDER, default="general")
    ap.add_argument("--src", choices=["th", "en"])
    ap.add_argument("--to", choices=["th", "en"])
    ap.add_argument("--model")
    ap.add_argument("--minimized", action="store_true", help="เปิดแบบย่อหน้าต่าง (สำหรับ Startup)")
    ap.add_argument("--tts", metavar="TEXT", help="ทดสอบเสียงอ่าน: สังเคราะห์และเล่นข้อความนี้")
    ap.add_argument("--ask", metavar="QUESTION", help="(ใช้กับ --cli) ถามคำถามเกี่ยวกับข้อความหลังแปล")
    ap.add_argument("text", nargs="?")
    a = ap.parse_args()
    if a.cli:
        sys.exit(run_cli(a))
    if a.tts:
        lang = detect_lang(a.tts)
        v = "th-TH-PremwadeeNeural" if lang == "th" else "en-US-JennyNeural"
        t = apply_replacements(a.tts, load_replacements()) if lang == "th" else a.tts
        p = tts_synthesize(t, v); print("audio:", p, os.path.getsize(p), "bytes")
        pl = Player(); pl.play(p)
        while pl.is_playing():
            time.sleep(0.2)
        pl.stop(); sys.exit(0)
    run_gui(minimized=a.minimized)
