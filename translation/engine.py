#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py - เครื่องมือแปลภาษา: การตั้งค่า, การเชื่อมต่อ Ollama (โมเดลในเครื่อง),
ผู้ให้บริการ API ออนไลน์สำรอง (OpenAI-compatible), และโหมด CLI
แยกออกจาก translator.py เพื่อให้ทดสอบ/แก้ไขส่วนตรรกะการแปลได้โดยไม่ต้องแตะ GUI
"""
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)


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
    except Exception as e:
        log.debug("เชื่อมต่อ Ollama ที่ %s ไม่ได้: %s", OLLAMA_URL, e)
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
        log.warning("เปิด Ollama (%s) ไม่สำเร็จ", exe, exc_info=True)
        return None
    for _ in range(wait_s * 2):
        time.sleep(0.5)
        models = list_models()
        if models is not None:
            log.info("เปิด Ollama (%s) สำเร็จ พบ %d โมเดล", exe, len(models))
            return models
    log.warning("เปิด Ollama (%s) แล้วแต่รอ %ds ไม่เชื่อมต่อสำเร็จ", exe, wait_s)
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
