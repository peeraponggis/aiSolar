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

LANGS = {"th": "Thai", "en": "English", "lo": "Lao"}
LANG_LABELS = {"th": "ไทย", "en": "อังกฤษ", "lo": "ลาว"}
THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
LAO_RE = re.compile(r"[\u0E80-\u0EFF]")
THINK_RE = re.compile(r"<think>.*?</think>\s*", re.S)


def detect_lang(text):
    """ตรวจภาษาต้นทางจากสัดส่วนอักษร: ลาว (U+0E80-0EFF) > ไทย > อังกฤษ"""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "th"
    lao = sum(1 for c in letters if LAO_RE.match(c))
    if lao / len(letters) > 0.3:
        return "lo"
    thai = sum(1 for c in letters if THAI_RE.match(c))
    return "th" if thai / len(letters) > 0.3 else "en"


def default_dst(src):
    """ปลายทางเริ่มต้นเมื่อไม่ได้บังคับทิศทาง: ไทย→อังกฤษ, อังกฤษ→ไทย, ลาว→ไทย"""
    return "en" if src == "th" else "th"


def needs_online(src, dst):
    """ทิศทางที่โมเดล 4B ในเครื่องทำไม่ได้ (ทดสอบ 19 ต.ค. 2569: Typhoon/Qwen 4-7B เขียนลาวผิดเพี้ยน) -> ควรใช้ API ออนไลน์"""
    return dst == "lo"


# ---------------------------------------------------------------- glossary
def load_glossary():
    """อ่าน glossary.txt -> list ของ (level หรือ None, คำไทย, คำแปล, ภาษาของคำแปล "en"/"lo")
    หัวข้อ [lao] = คู่ ไทย => ລາວ ใช้กับทุกระดับ; หัวข้อระดับอื่น/[all] กลับเป็นคู่ ไทย => อังกฤษ"""
    entries = []
    if not os.path.exists(GLOSSARY_FILE):
        return entries
    level, pair = None, "en"
    with open(GLOSSARY_FILE, "r", encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^\[(\w+)\]$", line)
            if m:
                tag = m.group(1).lower()
                if tag in ("lao", "lo"):
                    level, pair = None, "lo"
                else:
                    level, pair = (None if tag in ("all", "global") else tag), "en"
                continue
            if "=>" not in line:
                continue
            a, b = [s.strip() for s in line.split("=>", 1)]
            if a and b:
                entries.append((level, a, b, pair))
    return entries


def glossary_for(text, src, level, entries, dst=None):
    """คืนเฉพาะคำศัพท์ที่ปรากฏในข้อความ เพื่อให้ prompt สั้น (เลือกคู่ภาษาให้ตรงกับ src/dst)"""
    dst = dst or default_dst(src)
    pair = "lo" if "lo" in (src, dst) else "en"
    low = text.lower()
    hits = []
    for e in entries:
        lv, th, other = e[0], e[1], e[2]
        if (e[3] if len(e) > 3 else "en") != pair:
            continue
        if lv and lv != level:
            continue
        if src == "th" and th in text:
            hits.append((th, other))
        elif src == "en" and pair == "en" and other.lower() in low:
            hits.append((other, th))
        elif src == "lo" and other in text:
            hits.append((other, th))
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
    if dst == "lo":
        sys_prompt += (
            "- The target language is Lao (ພາສາລາວ), the official language of Laos. Write the output in LAO SCRIPT ONLY "
            "(Unicode block U+0E80-U+0EFF: ກ ຂ ຄ ງ ຈ ສ ຊ ຍ ດ ຕ ຖ ທ ນ ບ ປ ຜ ຝ ພ ຟ ມ ຢ ຣ ລ ວ ຫ ອ ຮ ...). "
            "Thai script (ก ข ค ... U+0E00-U+0E7F) is a DIFFERENT writing system and must never appear in the output. "
            "Use natural modern Lao vocabulary and spelling as used in Vientiane (e.g. ບໍ່ not ไม่, ເຮັດ not ทำ, ເຈົ້າ as the polite particle), "
            "not Thai words transliterated into Lao letters.\n"
        )
    elif src == "lo":
        sys_prompt += "- The source text is Lao (ພາສາລາວ), not Thai; read it as Lao even though the scripts look similar.\n"
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
    "KKU gen.ai (มข.)": {
        "base": "https://gen.ai.kku.ac.th/okmd/api/v1",
        "models": ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gpt-5.4-mini", "deepseek-v4-flash", "claude-sonnet-5", "qwen3.7-plus"],
        "signup": "",
        "key_env": "KKU_API_KEY",
        "note": "เกตเวย์ AI ของ มข. (ตัวเดียวกับ AI-Bridge-Launcher) ใช้คีย์จากตัวแปร KKU_API_KEY ของ Windows อัตโนมัติ ไม่ต้องกรอก "
                "และไม่บันทึกคีย์ลงไฟล์ · แปลเร็วสุด: gemini-3.1-flash-lite (~1 วินาที) · คุณภาพสูง: claude-sonnet-5 / gpt-5.4-mini · "
                "เลี่ยง qwen3.6-flash (คิดยาวเงียบๆ ช้า ~8 วินาทีและเปลืองเครดิต)"},
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
# ศูนย์ผู้ให้บริการ (ทะเบียนกลางที่ Multi Tools จัดการ — ลุงพี AI / ลุงพี Agent ใช้ไฟล์เดียวกัน) ไม่มีคีย์ในไฟล์:
# คีย์อ่านจากตัวแปร Windows ตาม key_env · ผู้ให้บริการที่ไม่ใช้คีย์ (เช่น Pollinations) มี nokey=True
HUB_FILE = os.environ.get("LUNGPEE_PROVIDERS") or r"F:\LocalAI\shared\providers.json"
HUB_PREFIX = "🔗 "


def load_hub_presets():
    """เติมรายการจากทะเบียนกลางเข้า API_PRESETS (ชื่อขึ้นต้น 🔗) — เรียกซ้ำได้เมื่อเปิดหน้าต่างผู้ให้บริการ"""
    for k in [k for k in API_PRESETS if k.startswith(HUB_PREFIX)]:
        del API_PRESETS[k]
    try:
        with open(HUB_FILE, encoding="utf-8") as f:
            items = json.load(f).get("providers") or []
    except (OSError, ValueError):
        return 0
    n = 0
    for p in items:
        if not isinstance(p, dict) or not p.get("base") or p.get("enabled", True) is False or p.get("auth") == "anthropic":
            continue   # anthropic: /models ต้องใช้ header พิเศษ ใช้ผ่าน Multi Tools/ลุงพี AI แทน
        nokey = p.get("auth") == "none" or not p.get("key_env")
        tag = "/".join(t for t, ok in (("ฟรี", p.get("free")), ("เสียเงิน", p.get("paid"))) if ok)
        API_PRESETS[HUB_PREFIX + (p.get("name") or p["id"]) + (f" [{tag}]" if tag else "")] = {
            "base": p["base"].rstrip("/"), "models": [m for m in (p.get("models") or []) if isinstance(m, str)],
            "signup": p.get("signup") or "", "key_env": p.get("key_env") or "", "nokey": nokey,
            "note": ("จากศูนย์ผู้ให้บริการ (จัดการรายชื่อ/คีย์ใน Multi Tools → ตั้งค่า) · "
                     + ("ไม่ต้องใช้คีย์" if nokey else f"คีย์จากตัวแปร {p.get('key_env')} ของ Windows อัตโนมัติ ไม่ต้องกรอก"))}
        n += 1
    return n


load_hub_presets()
BACKEND = {"mode": "local", "base": "", "key": "", "model": ""}   # โหมดที่ใช้งานอยู่จริง (ตั้งโดย GUI)


def env_key(name):
    """อ่านคีย์จากตัวแปรผู้ใช้ของ Windows (โปรแกรมที่เปิดก่อนตั้งค่าตัวแปรจะไม่เห็นใน os.environ จึงอ่าน registry สำรอง)"""
    if not name:
        return ""
    if os.environ.get(name):
        return os.environ[name]
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0] or ""
    except OSError:
        return ""


def resolve_api_key(api):
    """คีย์ที่กรอกเองมาก่อน ถ้าเว้นว่างและผู้ให้บริการกำหนด key_env ไว้ ให้ใช้คีย์จากตัวแปร Windows นั้น"""
    api = api or {}
    return api.get("key") or env_key(API_PRESETS.get(api.get("preset"), {}).get("key_env"))


def preset_nokey(name):
    """ผู้ให้บริการที่ไม่ใช้คีย์ (เช่น Pollinations จากศูนย์ผู้ให้บริการ)"""
    return bool(API_PRESETS.get(name or "", {}).get("nokey"))


def api_ready(api):
    """ตั้งค่า API ครบพอจะใช้ได้: มี base + โมเดล และมีคีย์ (หรือผู้ให้บริการไม่ใช้คีย์)"""
    api = api or {}
    return bool(api.get("base") and api.get("model") and (resolve_api_key(api) or preset_nokey(api.get("preset"))))


def _auth_headers(key):
    return {"Authorization": "Bearer " + key} if key else {}


def list_models_openai(base, key, timeout=15):
    req = urllib.request.Request(base.rstrip("/") + "/models", headers={**_auth_headers(key), "User-Agent": "LocalTranslator/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8"))
    items = d.get("data") if isinstance(d, dict) else d
    return sorted(m.get("id") for m in (items or []) if isinstance(m, dict) and m.get("id"))


def stream_chat_openai(base, key, model, messages, temperature, stop_event=None):
    """generator แบบเดียวกับ stream_chat แต่คุยกับ API รูปแบบ OpenAI (chat/completions, SSE)"""
    msgs = [dict(m, content=m["content"].replace("/no_think", "").rstrip()) for m in messages]
    body = json.dumps({"model": model, "messages": msgs, "stream": True, "temperature": temperature}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json", **_auth_headers(key), "User-Agent": "LocalTranslator/1.0",
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


def chat_stream(model, messages, temperature, stop_event=None, backend=None):
    """ตัวเลือกเส้นทาง: โมเดลในเครื่อง (Ollama) หรือ API ออนไลน์ ตาม BACKEND ที่ GUI ตั้งไว้
    backend = dict รูปแบบเดียวกับ BACKEND เพื่อบังคับเส้นทางเฉพาะงานนี้ (เช่น ไทย→ลาว ต้องใช้ API)
    โหมดอัตโนมัติ (BACKEND['fallback_model'] = โมเดลในเครื่อง): ถ้า API ล้มก่อนตอบอะไรออกมา ถอยไปแปลด้วยโมเดลในเครื่องแทน"""
    b = backend or BACKEND
    if b["mode"] == "api":
        fallback = b.get("fallback_model")
        if not fallback:
            return (yield from stream_chat_openai(b["base"], b["key"], b["model"], messages, temperature, stop_event))
        gen = stream_chat_openai(b["base"], b["key"], b["model"], messages, temperature, stop_event)
        try:
            first = next(gen)
        except StopIteration as e:
            return e.value
        except Exception as e:
            log.warning("API %s ล้ม (%s) — ถอยไปใช้โมเดลในเครื่อง %s", b.get("model"), str(e)[:120], fallback)
            return (yield from stream_chat(fallback, messages, temperature, stop_event))
        yield first
        return (yield from gen)
    return (yield from stream_chat(model, messages, temperature, stop_event))


# ---------------------------------------------------------------- เพิ่มผู้ให้บริการเข้าศูนย์ผู้ให้บริการ (ทะเบียนกลาง)
HUB_PRESETS = {   # ชุดย่อของ Multi Tools core/provider_hub.py — ชื่อ/base/ตัวแปรคีย์ตรงกัน จึงใช้ร่วมกันได้
    "openrouter": {"name": "OpenRouter (หลายโมเดล มีแบบฟรี)", "base": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY",
                   "free": True, "paid": True, "signup": "https://openrouter.ai/keys",
                   "models": ["google/gemma-4-26b-a4b-it:free", "qwen/qwen3.8-27b:free", "qwen/qwen3-235b-a22b-2507"]},
    "groq": {"name": "Groq (เร็วมาก ฟรีจำกัด)", "base": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY",
             "free": True, "paid": True, "signup": "https://console.groq.com/keys", "models": ["llama-3.3-70b-versatile", "qwen/qwen3-32b"]},
    "gemini": {"name": "Google Gemini (ฟรีจำกัด)", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "key_env": "GEMINI_API_KEY",
               "free": True, "paid": True, "signup": "https://aistudio.google.com/apikey", "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite"]},
    "openai": {"name": "OpenAI", "base": "https://api.openai.com/v1", "key_env": "OPENAI_API_KEY",
               "free": False, "paid": True, "signup": "https://platform.openai.com/api-keys", "models": ["gpt-4o-mini", "gpt-4.1-mini"]},
    "typhoon": {"name": "OpenTyphoon (SCB10X ภาษาไทย)", "base": "https://api.opentyphoon.ai/v1", "key_env": "TYPHOON_API_KEY",
                "free": True, "paid": True, "signup": "https://opentyphoon.ai", "models": ["typhoon-v2.5-30b-a3b-instruct"]},
    "custom": {"name": "", "base": "", "key_env": "", "free": False, "paid": False, "signup": "", "models": []},
}
_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


def set_windows_key(env, value):
    """เก็บคีย์เป็นตัวแปรผู้ใช้ของ Windows (HKCU\\Environment) — ไม่ลงไฟล์/log"""
    value = (value or "").strip()
    if not _ENV_NAME_RE.match(env or ""):
        raise ValueError("ชื่อตัวแปรคีย์ต้องเป็นตัวพิมพ์ใหญ่/ตัวเลข/_ เช่น OPENROUTER_API_KEY")
    if not value or any(c in value for c in " \t\r\n\"'"):
        raise ValueError("คีย์ต้องไม่ว่างและไม่มีช่องว่าง/อัญประกาศ")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, env, 0, winreg.REG_SZ, value)
    os.environ[env] = value
    try:
        import ctypes
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 2, 3000, None)
    except Exception:
        pass


def hub_add_provider(preset, name="", base="", key_env="", key=""):
    """เพิ่มผู้ให้บริการลงทะเบียนกลาง (รูปแบบเดียวกับ Multi Tools) + ตั้งคีย์ถ้าให้มา คืนชื่อรายการใน API_PRESETS"""
    pre = HUB_PRESETS.get(preset) or HUB_PRESETS["custom"]
    name = (name or "").strip() or pre["name"]
    base = ((base or "").strip() or pre["base"]).rstrip("/")
    key_env = (key_env or "").strip() or pre["key_env"]
    if not name or not re.match(r"^https://|^http://(127\.0\.0\.1|localhost)[:/]", base):
        raise ValueError("ใส่ชื่อ และ Base URL ที่ขึ้นต้นด้วย https:// (ลงท้าย /v1)")
    if key_env and not _ENV_NAME_RE.match(key_env):
        raise ValueError("ชื่อตัวแปรคีย์ต้องเป็นตัวพิมพ์ใหญ่/ตัวเลข/_ เช่น OPENROUTER_API_KEY")
    try:
        with open(HUB_FILE, encoding="utf-8") as f:
            doc = json.load(f)
        items = doc.get("providers") or []
    except (OSError, ValueError):
        doc, items = {"version": 1}, [{"id": "kku", "preset": "kku", "name": "KKU gen.ai (มข.)", "base": "https://gen.ai.kku.ac.th/okmd/api/v1",
                                       "key_env": "KKU_API_KEY", "auth": "bearer", "models_url": None, "free": False, "paid": True,
                                       "signup": "https://gen.ai.kku.ac.th", "enabled": True,
                                       "models": ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gpt-5.4-mini", "deepseek-v4-flash", "claude-sonnet-5", "qwen3.7-plus"]}]
    pid, n = (preset if preset in HUB_PRESETS else "custom"), 2
    while any(p.get("id") == pid for p in items):
        pid, n = f"{preset}-{n}", n + 1
    item = {"id": pid, "preset": preset if preset in HUB_PRESETS else "custom", "name": name, "base": base, "key_env": key_env,
            "auth": "bearer" if key_env else "none", "models_url": None, "models": list(pre["models"]), "free": pre["free"], "paid": pre["paid"],
            "signup": pre["signup"], "enabled": True}
    items.append(item)
    doc.update(providers=items, updated=time.strftime("%Y-%m-%dT%H:%M:%S"), by="Local Translator",
               note="no API keys here — keys live in Windows user environment variables named by key_env")
    os.makedirs(os.path.dirname(HUB_FILE), exist_ok=True)
    tmp = HUB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.replace(tmp, HUB_FILE)
    if key and key_env:
        set_windows_key(key_env, key)
    load_hub_presets()
    tag = "/".join(t for t, ok in (("ฟรี", pre["free"]), ("เสียเงิน", pre["paid"])) if ok)
    return HUB_PREFIX + name + (f" [{tag}]" if tag else "")


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
def api_backend(settings):
    """คืน dict เส้นทาง API ออนไลน์จาก settings['api'] (รูปแบบเดียวกับ BACKEND) หรือ None ถ้ายังไม่ได้ตั้งค่าครบ"""
    a = (settings or {}).get("api") or {}
    if api_ready(a):
        return {"mode": "api", "base": a["base"], "key": resolve_api_key(a), "model": a["model"]}
    return None


def load_settings_file():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def run_cli(args):
    for stream in (sys.stdout, sys.stderr):   # console ไทย (cp874) พิมพ์อักษรลาวไม่ได้ - บังคับ UTF-8 กันโปรแกรมล้มใน --cli
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    text = args.text or sys.stdin.read()
    src = args.src or detect_lang(text)
    dst = args.to or default_dst(src)
    api = api_backend(load_settings_file())
    use_api = bool(api) and (needs_online(src, dst) or args.model == "api")
    if use_api:   # ไทย/อังกฤษ→ลาว: ใช้ผู้ให้บริการออนไลน์ก่อนเสมอ (หรือบังคับด้วย --model api)
        model = api["model"]
        gen_fn = lambda msgs, temp: stream_chat_openai(api["base"], api["key"], api["model"], msgs, temp)
        print(f"[ใช้ผู้ให้บริการออนไลน์ {api['base']}]", file=sys.stderr)
    else:
        models = ensure_ollama()   # เปิด Ollama ให้เองถ้ายังไม่ทำงาน (เหมือนโหมดหน้าต่าง)
        if models is None:
            print("เชื่อมต่อ Ollama ไม่ได้ที่", OLLAMA_URL, "- ติดตั้ง Ollama จาก https://ollama.com/download แล้วลองใหม่", file=sys.stderr)
            return 2
        model = (args.model if args.model and args.model != "api" else None) or pick_model(models)
        gen_fn = lambda msgs, temp: stream_chat(model, msgs, temp)
        if needs_online(src, dst):
            print("คำเตือน: โมเดลในเครื่องแปลเป็นภาษาลาวได้ไม่ดี (เขียนผิดเพี้ยน) - ตั้งค่า ⚙ ผู้ให้บริการ (settings.json) เพื่อใช้ API ออนไลน์", file=sys.stderr)
    hits = glossary_for(text, src, args.level, load_glossary(), dst)
    msgs = build_messages(text, src, dst, args.level, hits)
    print(f"[{model}] {src}->{dst} level={args.level} glossary={len(hits)}", file=sys.stderr)
    out = []
    t0 = time.time()
    gen = gen_fn(msgs, LEVELS[args.level]["temp"])
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
        gen = gen_fn(qmsgs, 0.4)
        try:
            while True:
                sys.stdout.write(next(gen)); sys.stdout.flush()
        except StopIteration:
            pass
