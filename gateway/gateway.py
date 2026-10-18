#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LocalAI Unified Gateway - Single entry point for all services
Merges: TTS, RAG, File Access, Clip Generation, Config, Proxy, Static Files
Routes:
  /api/chat       -> Ollama chat completion (proxy)
  /api/generate   -> Ollama generate (proxy)
  /api/embeddings -> Ollama embeddings (proxy)
  /api/tags       -> Ollama list models (proxy)
  /api/pull       -> Ollama pull model (proxy)
  /api/tts        -> Edge TTS (Thai neural voices)
  /api/voices     -> List Thai voices
  /api/rag/search -> RAG semantic search
  /api/rag/status -> RAG index status
  /api/rag/reindex-> Rebuild RAG index
  /api/clip       -> Generate video clip
  /api/file       -> Read local file/folder
  /api/config     -> Load/Save config (model.md)
  /api/proxy      -> Fetch web content (bypass CORS)
  /health         -> Health check
  /*              -> Static files (chat.html, lib/*)
"""
import asyncio
import json
import os
import re
import sys
import time
import hashlib
import threading
import urllib.request
import urllib.parse
import urllib.error
import gzip
import zlib
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import edge_tts

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ============================================================
# CONFIGURATION
# ============================================================
HOST, PORT = "127.0.0.1", 11435
OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_VOICE = "th-TH-PremwadeeNeural"
EMBED_MODEL = "bge-m3:latest"

BASE = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS') else (Path(sys.argv[0]).parent if getattr(sys, 'frozen', False) else Path(__file__).parent)
UI_DIR = BASE / "ui"
KNOWLEDGE_DIR = BASE / "knowledge"
CACHE_FILE = KNOWLEDGE_DIR / ".rag_cache.json"

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".gif": "image/gif",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".map": "application/json",
}

# ============================================================
# RAG STATE (in-process)
# ============================================================
_index = {"chunks": [], "vecs": [], "sources": [], "indexed_at": None, "files": 0}
_index_lock = threading.Lock()
EXTS = {".md", ".txt", ".csv", ".log", ".json"}

# ============================================================
# UTILITY FUNCTIONS
# ============================================================
def _cors_headers(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "*")

def _send_json(handler, obj, code=200):
    body = json.dumps(obj, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)

def _send_json_line(handler, obj, code=200):
    # /api/chat ไม่สตรีม: ส่ง JSON หนึ่งบรรทัดปิดท้ายด้วย \n เหมือน NDJSON ของ Ollama
    # หน้าเว็บที่อ่านแบบสตรีม (แยกบรรทัด) จะได้ไม่ค้างรอบรรทัดสุดท้าย
    body = json.dumps(obj, ensure_ascii=False).encode() + b"\n"
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)

def _send_bytes(handler, body, ctype, code=200):
    handler.send_response(code)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)

def _send_text(handler, text, code=200):
    body = text.encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    _cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(body)

def _send_error(handler, msg, code=500):
    _send_json(handler, {"error": msg}, code)

# ============================================================
# OLLAMA PROXY
# ============================================================
def _parse_ollama_response(raw_bytes):
    # Ollama บางครั้งส่ง JSON หลายก้อนต่อกันโดยไม่ขึ้นบรรทัดใหม่ (หรือมีขึ้นบรรทัดในเนื้อหา)
    # จึงถอดทีละก้อนด้วย raw_decode แทนการแยกด้วย \n
    text = raw_bytes.decode("utf-8", "replace").strip()
    if not text:
        return None
    decoder = json.JSONDecoder()
    results = []
    idx, n = 0, len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        results.append(obj)
        idx = end
    if len(results) == 1:
        return results[0]
    merged = {}
    for r in results:
        for k, v in r.items():
            if k == "message":
                if "message" not in merged:
                    merged["message"] = v
                elif "content" in v:
                    merged["message"]["content"] = merged["message"].get("content", "") + v["content"]
                elif "role" in v:
                    merged["message"].update(v)
            else:
                merged[k] = v
    return merged

def ollama_request(method, path, data=None, timeout=120):
    url = OLLAMA_HOST + path
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return _parse_ollama_response(raw)

# ============================================================
# EDGE TTS
# ============================================================
async def _synth(text, voice, rate):
    audio = bytearray()
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return bytes(audio)

async def _list_thai_voices():
    voices = await edge_tts.list_voices()
    return [
        {"name": v["ShortName"], "gender": v.get("Gender", ""), "locale": v.get("Locale", "")}
        for v in voices if v.get("Locale", "").startswith("th")
    ]

# ============================================================
# RAG FUNCTIONS (in-process, from rag_server.py)
# ============================================================
def read_pdf(path):
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    except Exception as e:
        print(f"  PDF read failed {path.name}: {e}")
        return ""

def read_file(path):
    if path.suffix.lower() == ".pdf":
        return read_pdf(path)
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""

def chunk_text(t, size=800, overlap=120):
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 > size and cur:
            chunks.append(cur)
            cur = (cur[-overlap:] + "\n\n" + p) if overlap else p
        else:
            cur = cur + "\n\n" + p if cur else p
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) > 40] or ([t[:size]] if t.strip() else [])

def embed(text):
    # num_gpu:0 บังคับรันบน CPU กัน bge-m3 แย่งที่โมเดลแชทใน VRAM (การ์ด 4GB ใส่พร้อมกันไม่พอ ทำให้ Ollama evict สลับไปมา)
    for attempt in range(3):
        try:
            req = urllib.request.Request(OLLAMA_HOST + "/api/embeddings",
                data=json.dumps({"model": EMBED_MODEL, "prompt": text, "options": {"num_gpu": 0}}).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())["embedding"]
        except Exception as e:
            if attempt < 2:
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            print(f"Embedding failed after retries: {e}")
            raise

def cosine(a, b):
    d = sum(x*y for x, y in zip(a, b))
    na = sum(x*x for x in a) ** 0.5
    nb = sum(y*y for y in b) ** 0.5
    return d/(na*nb) if na and nb else 0.0

def file_sig(p):
    st = p.stat()
    return f"{int(st.st_mtime)}_{st.st_size}"

def build_index(force=False, log=print):
    KNOWLEDGE_DIR.mkdir(exist_ok=True)
    files = [p for p in KNOWLEDGE_DIR.rglob("*")
             if p.is_file() and not p.name.startswith(".")
             and (p.suffix.lower() in EXTS or p.suffix.lower() == ".pdf")
             and not any(part.startswith(".") for part in p.relative_to(KNOWLEDGE_DIR).parts[:-1])]
    
    cache = {}
    if CACHE_FILE.exists() and not force:
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    cached_files = cache.get("files", {})

    chunks, vecs, sources = [], [], []
    new_cache_files = {}
    for p in files:
        sig = file_sig(p)
        key = str(p)
        if key in cached_files and cached_files[key]["sig"] == sig:
            e = cached_files[key]
            log(f"  cache: {p.name} ({len(e['chunks'])} chunks)")
        else:
            text = read_file(p)
            cks = chunk_text(text)
            log(f"  embed: {p.name} ({len(cks)} chunks)...")
            cvs = []
            for ci, c in enumerate(cks, 1):
                try:
                    cvs.append(embed(c))
                except Exception as ex:
                    log(f"     embed fail: {ex}")
                    cvs.append(None)
                log(f"     ...{ci}/{len(cks)}")
                sys.stdout.flush()
            pairs = [(c, v) for c, v in zip(cks, cvs) if v]
            e = {"sig": sig, "chunks": [c for c, _ in pairs], "vecs": [v for _, v in pairs]}
        new_cache_files[key] = e
        for c, v in zip(e["chunks"], e["vecs"]):
            chunks.append(c)
            vecs.append(v)
            sources.append(p.name)

    with _index_lock:
        _index.update(chunks=chunks, vecs=vecs, sources=sources,
                      indexed_at=time.strftime("%Y-%m-%d %H:%M:%S"), files=len(files))
    CACHE_FILE.write_text(json.dumps({"files": new_cache_files}, ensure_ascii=False), encoding="utf-8")
    log(f"index done: {len(chunks)} chunks from {len(files)} files")

def rag_search(q, k=4):
    qv = embed(q)
    with _index_lock:
        scored = sorted(
            ({"text": c, "source": s, "score": cosine(qv, v)}
             for c, v, s in zip(_index["chunks"], _index["vecs"], _index["sources"])),
            key=lambda x: -x["score"])
    return scored[:k]

# ============================================================
# CLIP GENERATION (delegates to clipgen.py)
# ============================================================
def make_clip(scenes, voice, fmt="portrait", subtitle=True, music=None):
    import clipgen
    import importlib
    importlib.reload(clipgen)
    
    ffmpeg = BASE / "tools" / "ffmpeg" / "ffmpeg.exe"
    if not ffmpeg.exists():
        ffmpeg = "ffmpeg"
    
    workdir = BASE / "clips" / "_work"
    out = BASE / "clips" / f"gen_{int(time.time())}.mp4"
    
    if music == "default":
        music = BASE / "tools" / "music" / "ambient.mp3"
    
    clipgen.make_clip(scenes[:12], voice, str(ffmpeg), str(workdir), str(out), 
                      fmt=fmt, subtitle=subtitle, music=str(music) if music else None)
    return out

# ============================================================
# FILE ACCESS
# ============================================================
def read_local_file(path_str):
    if not path_str:
        return None, "missing path"
    
    path = Path(path_str)
    if path.is_dir():
        entries = []
        for name in sorted(os.listdir(path)):
            fp = path / name
            kind = "folder" if fp.is_dir() else f"{fp.stat().st_size} bytes"
            entries.append(f"{name}  ({kind})")
        return f"[folder: {path}]\n" + "\n".join(entries), None
    
    if not path.is_file():
        return None, f"not found: {path}"
    
    size = path.stat().st_size
    if size > 5 * 1024 * 1024:
        return None, f"file too large: {size} bytes"
    
    ext = path.suffix.lower()
    if ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            out = []
            for ws in wb.worksheets:
                out.append(f"[sheet: {ws.title}]")
                for row in ws.iter_rows(values_only=True):
                    out.append(",".join("" if c is None else str(c) for c in row))
            return "\n".join(out), None
        except ImportError:
            return None, "openpyxl not installed"
    
    with open(path, "rb") as f:
        raw = f.read()
    
    for enc in ("utf-8-sig", "utf-8", "cp874", "tis-620", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    else:
        text = raw.decode("latin-1", "replace")
    
    if "<table" in text.lower() or "<tr" in text.lower():
        text = html_table_to_text(text)
    
    return text, None

def html_table_to_text(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    rows = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html)
    out = []
    for r in rows:
        cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", r)
        cells = [re.sub(r"(?s)<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in cells]
        if any(cells):
            out.append(" | ".join(cells))
    return "\n".join(out) if out else re.sub(r"(?s)<[^>]+>", " ", html)

# ============================================================
# WEB PROXY (bypass CORS)
# ============================================================
def fetch_url(url):
    if not url or not url.startswith(("http://", "https://")):
        return None, "invalid url"
    
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "th,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
    })
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            final_url = resp.geturl()
            raw = resp.read(200 * 1024)
            enc = resp.headers.get("Content-Encoding", "")
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                raw = zlib.decompress(raw)
            
            ctype = resp.headers.get("Content-Type", "")
            m = re.search(r"charset=([\w-]+)", ctype)
            charset = m.group(1) if m else "utf-8"
            try:
                html = raw.decode(charset, "replace")
            except Exception:
                html = raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, f"fetch failed: {e}"
    
    # Extract text
    html = re.sub(r"(?is)<(script|style|nav|aside|footer|header|svg|form|noscript|iframe)[^>]*>.*?</\1>", " ", html)
    
    title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    desc_m = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html)
    og_m = re.search(r'(?is)<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']', html)
    
    title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
    desc = (desc_m.group(1) if desc_m else (og_m.group(1) if og_m else "")).strip()
    
    article_m = re.search(r"(?is)<article[^>]*>(.*?)</article>", html)
    main_m = re.search(r"(?is)<main[^>]*>(.*?)</main>", html)
    body = article_m.group(1) if article_m else (main_m.group(1) if main_m else html)
    
    body = re.sub(r"(?is)<(br|hr)\s*/?>", "\n", body)
    body = re.sub(r"(?is)</(p|div|li|h[1-6]|section|article|blockquote|tr)>", "\n", body)
    body = re.sub(r"(?is)<li[^>]*>", "\n• ", body)
    text = re.sub(r"(?s)<[^>]+>", " ", body)
    
    html_entities = {"&nbsp;": " ", "&": "&", "<": "<", ">": ">",
                     "\u201d": '"', "\u2019": "'", "&apos;": "'", "&mdash;": "\u2014",
                     "&ndash;": "\u2013", "&hellip;": "\u2026", "&laquo;": "\u00ab", "&raquo;": "\u00bb",
                     "&ldquo;": "\u201c", "&rdquo;": "\u201d", "&lsquo;": "\u2018", "&rsquo;": "\u2019"}
    for k, v in html_entities.items():
        text = text.replace(k, v)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    
    header = ""
    if title:
        header += f"Title: {title}\n"
    if desc and desc not in text[:500]:
        header += f"Description: {desc}\n"
    header += f"URL: {final_url}\n\n"
    
    MAX = 15000
    if len(text) > MAX:
        text = text[:MAX] + f"\n\n[...truncated at {MAX} chars...]"
    
    return header + text, None

# ============================================================
# CONFIG (model.md)
# ============================================================
CONFIG_PATH = BASE / "model.md"

def load_config():
    if not CONFIG_PATH.exists():
        return None, "no saved config"
    try:
        content = CONFIG_PATH.read_text(encoding="utf-8")
        m = re.search(r"```json\s*\n([\s\S]*?)\n```", content)
        if not m:
            return None, "no JSON block in model.md"
        return json.loads(m.group(1)), None
    except Exception as e:
        return None, str(e)

def save_config(data):
    if not isinstance(data, dict):
        return None, "cfg must be object"
    
    import time
    lines = [
        "# LocalAI Config Backup",
        "",
        "> ⚠️ This file stores API keys in plaintext — do not upload/share",
        "> Auto-updated every time Settings change in chat.html",
        "",
        f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"## Providers ({len(data.get('providers') or [])})",
        "",
    ]
    
    for i, p in enumerate(data.get("providers") or [], 1):
        lines.append(f"### {i}. {p.get('label') or '-'}")
        lines.append(f"- **Base URL:** {p.get('baseUrl') or '-'}")
        key = p.get("apiKey") or ""
        masked = (key[:8] + "…" + key[-4:]) if len(key) > 16 else ("(set)" if key else "(empty)")
        lines.append(f"- **API Key:** `{masked}` (full in JSON block below)")
        models = p.get("models") or []
        if isinstance(models, list):
            lines.append(f"- **Models ({len(models)}):** {', '.join(models[:20])}{' …' if len(models) > 20 else ''}")
        else:
            lines.append(f"- **Models:** {models}")
        lines.append("")
    
    lines.extend([
        "## Settings",
        "",
        "| Key | Value |",
        "|-----|-------|",
    ])
    
    for k in ("system", "ctx", "temp", "topK", "ragOn", "ttsEngine", "neuralVoice",
              "voiceRate", "ttsUrl", "ollamaUrl", "freeOnline", "autoFallback"):
        v = data.get(k)
        if v is None:
            continue
        sv = str(v)
        if len(sv) > 80:
            sv = sv[:80] + "…"
        lines.append(f"| {k} | {sv.replace('|', '\\|').replace('\n', ' ')} |")
    
    lines.extend([
        "",
        "## Raw JSON (used for restore)",
        "",
        "```json",
        json.dumps(data, ensure_ascii=False, indent=2),
        "```",
    ])
    
    CONFIG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(CONFIG_PATH)}, None

# ============================================================
# STATIC FILE SERVING
# ============================================================
def serve_static(handler, path):
    rel = unquote(path.lstrip("/")) or "chat.html"
    if rel in ("", "/"):
        rel = "chat.html"
    full = (UI_DIR / rel).resolve()
    if not str(full).startswith(str(UI_DIR.resolve())) or not full.is_file():
        _send_error(handler, "not found", 404)
        return
    ctype = MIME.get(full.suffix.lower(), "application/octet-stream")
    with open(full, "rb") as f:
        _send_bytes(handler, f.read(), ctype)

# ============================================================
# HTTP HANDLER
# ============================================================
# ============================================================
# KKU gen.ai (มข.) — OpenAI-compatible, คีย์อยู่ฝั่ง server เท่านั้น
# ============================================================
KKU_BASE = os.environ.get("KKU_API_BASE", "https://gen.ai.kku.ac.th/okmd/api/v1").rstrip("/")
KKU_PATHS = {("GET", "/v1/models"), ("POST", "/v1/chat/completions")}
SAME_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}


def _kku_key():
    # อ่านจาก registry สำรอง เพราะ gateway ที่เปิดก่อนตั้งตัวแปรจะไม่เห็นใน os.environ
    key = os.environ.get("KKU_API_KEY")
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, "KKU_API_KEY")[0] or ""
    except OSError:
        return ""


def _same_origin(handler):
    # ปลายทางนี้ใช้เครดิต KKU ของผู้ใช้ -> รับเฉพาะหน้าแชทของ gateway เอง (หรือโปรแกรมในเครื่องที่ไม่มี Origin)
    origin = handler.headers.get("Origin")
    if origin and origin not in SAME_ORIGINS:
        return False
    return handler.headers.get("Sec-Fetch-Site") != "cross-site"


def kku_proxy(handler, method, sub, body=None):
    if not _same_origin(handler):
        _send_error(handler, "forbidden origin", 403); return
    key = _kku_key()
    if sub == "/status":
        _send_json(handler, {"available": bool(key), "base": KKU_BASE}); return
    if (method, sub) not in KKU_PATHS:
        _send_error(handler, "not allowed", 404); return
    if not key:
        _send_error(handler, "ยังไม่ได้ตั้งตัวแปร KKU_API_KEY ของ Windows", 503); return
    req = urllib.request.Request(KKU_BASE + sub[len("/v1"):], data=body, method=method, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "Accept": handler.headers.get("Accept") or "*/*"})
    try:
        resp = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        _send_bytes(handler, e.read(), e.headers.get("Content-Type") or "application/json", e.code); return
    except urllib.error.URLError as e:
        _send_error(handler, f"เชื่อมต่อ KKU ไม่ได้: {e.reason}", 502); return
    with resp:
        handler.send_response(resp.status)
        handler.send_header("Content-Type", resp.headers.get("Content-Type") or "application/json")
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        while True:   # ส่งต่อทีละก้อนทันทีที่ได้ เพื่อให้ SSE สตรีมถึงหน้าแชทแบบเรียลไทม์
            chunk = resp.read1(8192)
            if not chunk:
                break
            handler.wfile.write(chunk)
            handler.wfile.flush()


class GatewayHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    
    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()
    
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        
        try:
            if u.path.startswith("/api/kku/"):
                kku_proxy(self, "GET", u.path[len("/api/kku"):])

            # Health
            elif u.path == "/health":
                _send_bytes(self, b"ok", "text/plain")
            
            # Ollama Proxy
            elif u.path == "/api/tags":
                data = ollama_request("GET", "/api/tags")
                _send_json(self, data)
            
            # TTS
            elif u.path == "/api/voices":
                data = asyncio.run(_list_thai_voices())
                _send_json(self, data)
            elif u.path == "/api/tts":
                text = unquote(q.get("text", [""])[0])
                voice = q.get("voice", [DEFAULT_VOICE])[0]
                rate = q.get("rate", ["+0%"])[0]
                if not text.strip():
                    _send_error(self, "missing text", 400)
                    return
                audio = asyncio.run(_synth(text, voice, rate))
                _send_bytes(self, audio, "audio/mpeg")
            
            # RAG
            elif u.path == "/api/rag/status":
                with _index_lock:
                    _send_json(self, {
                        "chunks": len(_index["chunks"]),
                        "files": _index["files"],
                        "indexed_at": _index["indexed_at"]
                    })
            elif u.path == "/api/rag/search":
                query = (q.get("q") or [""])[0]
                k = int((q.get("k") or ["4"])[0])
                if not query:
                    _send_json(self, {"hits": []})
                    return
                try:
                    hits = rag_search(query, k)
                    _send_json(self, {"hits": hits})
                except Exception as e:
                    _send_error(self, str(e), 500)
            
            # Config
            elif u.path == "/api/config":
                data, err = load_config()
                if err:
                    _send_error(self, err, 404 if "no saved" in err else 500)
                else:
                    _send_json(self, data)
            
            # File access
            elif u.path == "/api/file":
                path = unquote(q.get("path", [""])[0])
                text, err = read_local_file(path)
                if err:
                    _send_error(self, err, 404 if "not found" in err else 400)
                else:
                    _send_text(self, text)
            
            # Web proxy
            elif u.path == "/api/proxy":
                url = unquote(q.get("url", [""])[0])
                text, err = fetch_url(url)
                if err:
                    _send_error(self, err, 502)
                else:
                    _send_text(self, text)
            
            # Ollama proxy catch-all (only for /api/ paths not matched above)
            elif u.path.startswith("/api/"):
                try:
                    data = ollama_request("GET", u.path)
                    _send_json(self, data)
                except Exception as e:
                    _send_error(self, f"Ollama proxy error: {e}", 502)
            
            # Static files
            else:
                serve_static(self, u.path)
        
        except Exception as e:
            _send_error(self, f"GET error: {e}")
    
    def do_POST(self):
        u = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else ""
            data = json.loads(body) if body else {}
        except Exception:
            data = {}
        
        try:
            if u.path.startswith("/api/kku/"):
                kku_proxy(self, "POST", u.path[len("/api/kku"):], json.dumps(data).encode("utf-8"))

            # Ollama Proxy
            elif u.path in ("/api/chat", "/api/generate", "/api/embeddings", "/api/pull"):
                if u.path == "/api/chat" and "stream" not in data:
                    data["stream"] = False
                ollama_data = ollama_request("POST", u.path, data, timeout=300)
                if u.path == "/api/chat":
                    _send_json_line(self, ollama_data)
                else:
                    _send_json(self, ollama_data)
            
            # TTS
            elif u.path == "/api/tts":
                text = (data.get("text") or "").strip()
                voice = data.get("voice") or DEFAULT_VOICE
                rate = data.get("rate") or "+0%"
                if not text:
                    _send_error(self, "missing text", 400)
                    return
                audio = asyncio.run(_synth(text, voice, rate))
                _send_bytes(self, audio, "audio/mpeg")
            
            # Clip generation
            elif u.path == "/api/clip":
                scenes = data.get("scenes") or []
                if not scenes:
                    _send_error(self, "no scenes", 400)
                    return
                try:
                    voice = data.get("voice") or DEFAULT_VOICE
                    fmt = data.get("format") or "portrait"
                    subtitle = data.get("subtitle", True)
                    music = data.get("music")
                    out_path = make_clip(scenes, voice, fmt, subtitle, music)
                    with open(out_path, "rb") as f:
                        _send_bytes(self, f.read(), "video/mp4")
                except Exception as e:
                    _send_error(self, f"clip generation failed: {e}", 500)
            
            # Config save
            elif u.path == "/api/config":
                result, err = save_config(data)
                if err:
                    _send_error(self, err, 400 if "must be object" in err else 500)
                else:
                    _send_json(self, result)
            
            # RAG reindex
            elif u.path == "/api/rag/reindex":
                threading.Thread(target=lambda: build_index(force=True), daemon=True).start()
                _send_json(self, {"ok": True, "msg": "reindexing..."})
            
            else:
                _send_error(self, "not found", 404)
        
        except Exception as e:
            _send_error(self, f"POST error: {e}")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print(f"LocalAI Unified Gateway on http://{HOST}:{PORT}")
    print("Endpoints:")
    print("  /api/chat, /api/generate, /api/embeddings, /api/tags, /api/pull -> Ollama")
    print("  /api/tts, /api/voices -> Edge TTS")
    print("  /api/rag/search, /api/rag/status, /api/rag/reindex -> RAG")
    print("  /api/clip -> Video generation")
    print("  /api/file -> Local file access")
    print("  /api/config -> Config load/save")
    print("  /api/proxy -> Web content fetch")
    print("  /health -> Health check")
    print("  /* -> Static files (chat.html)")
    print()
    # Start RAG index build in background (non-blocking)
    threading.Thread(target=lambda: build_index(), daemon=True).start()
    print("Starting server...")
    ThreadingHTTPServer((HOST, PORT), GatewayHandler).serve_forever()