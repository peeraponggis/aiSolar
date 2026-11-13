# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

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

from app_version import about_text, info as version_info

if sys.stdout is None or sys.stderr is None:
    # build แบบไม่มีหน้าต่าง console: เก็บข้อความ print ลงไฟล์ข้าง exe แทน (หมุนไฟล์เมื่อเกิน 2 MB)
    _log_path = Path(sys.executable).with_name("gateway.log")
    try:
        if _log_path.exists() and _log_path.stat().st_size > 2_000_000:
            _log_path.replace(_log_path.with_name("gateway.log.1"))
        sys.stdout = sys.stderr = open(_log_path, "a", encoding="utf-8", buffering=1)
    except OSError:
        pass

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
def ocr_sidecar(path):
    """ผล OCR ของ PDF (สร้างด้วย ocr_knowledge.py) เก็บที่ knowledge\\.ocr\\<path>.json — โฟลเดอร์ซ่อน ไม่ถูกจัดเข้าคลังเอง"""
    try:
        return KNOWLEDGE_DIR / ".ocr" / (str(path.relative_to(KNOWLEDGE_DIR)) + ".json")
    except ValueError:
        return None

def _ocr_pages(path):
    side = ocr_sidecar(path)
    if not side or not side.is_file():
        return {}
    try:
        d = json.loads(side.read_text(encoding="utf-8"))
    except Exception:
        return {}
    st = path.stat()
    if d.get("sig") != f"{int(st.st_mtime)}_{st.st_size}":   # PDF เปลี่ยนหลังทำ OCR: ผลเก่าใช้ไม่ได้
        return {}
    return {int(k): v for k, v in (d.get("pages") or {}).items()}

def read_pdf(path):
    # หน้าที่เป็นภาพสแกน/ฟอนต์ไทยรุ่นเก่าที่ถอดเป็นอักษรเพี้ยน ใช้ข้อความ OCR แทน (ถ้ามี) หน้าอื่นใช้ข้อความในไฟล์ตามเดิม
    try:
        from pypdf import PdfReader
        ocr = _ocr_pages(path)
        return "\n".join(ocr[i] if i in ocr else (pg.extract_text() or "")
                         for i, pg in enumerate(PdfReader(str(path)).pages))
    except Exception as e:
        print(f"  PDF read failed {path.name}: {e}")
        return ""

# PDF ภาษาไทยรุ่นเก่า (ฟอนต์ Windows) เก็บสระบน/ล่างและวรรณยุกต์เป็นรหัส Private Use (U+F700–F71A)
# เช่น "ไฟฟา" = "ไฟฟ้า" — ถ้าไม่แปลงกลับ คำค้นภาษาไทยจะไม่ตรงกับเนื้อหา
THAI_PUA = str.maketrans({
    0xF700: "ฐ", 0xF701: "ิ", 0xF702: "ี", 0xF703: "ึ", 0xF704: "ื", 0xF705: "่", 0xF706: "้", 0xF707: "๊",
    0xF708: "๋", 0xF709: "์", 0xF70A: "่", 0xF70B: "้", 0xF70C: "๊", 0xF70D: "๋", 0xF70E: "์", 0xF70F: "ญ",
    0xF710: "ั", 0xF711: "ํ", 0xF712: "็", 0xF713: "่", 0xF714: "้", 0xF715: "๊", 0xF716: "๋", 0xF717: "์",
    0xF718: "ุ", 0xF719: "ู", 0xF71A: "ฺ",
})

def read_file(path):
    if path.suffix.lower() == ".pdf":
        return read_pdf(path).translate(THAI_PUA)
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore").translate(THAI_PUA)
    except Exception:
        return ""

def _split_long(p, size):
    """ย่อหน้าที่ยาวเกิน size (ตาราง/CSV ที่ไม่มีบรรทัดว่างคั่น): ตัดตามบรรทัด แล้วตามช่องว่าง/ความยาว
    — เดิมทั้งก้อน 7,000–70,000 ตัวอักษรเป็นท่อนเดียว เกินความยาวที่ bge-m3 รับได้ Ollama ตอบ HTTP 500"""
    if len(p) <= size:
        return [p]
    out, cur = [], ""
    for line in p.split("\n"):
        while len(line) > size:   # บรรทัดเดียวยาวเกิน: ตัดที่ช่องว่างใกล้ size ที่สุด
            cut = line.rfind(" ", size // 2, size)
            cut = cut if cut > 0 else size
            if cur:
                out.append(cur); cur = ""
            out.append(line[:cut]); line = line[cut:].lstrip()
        if cur and len(cur) + len(line) + 1 > size:
            out.append(cur); cur = line
        else:
            cur = cur + "\n" + line if cur else line
    if cur:
        out.append(cur)
    return out

def chunk_text(t, size=800, overlap=120):
    paras = [s for p in re.split(r"\n\s*\n", t) if p.strip() for s in _split_long(p.strip(), size)]
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
    sig = f"{int(st.st_mtime)}_{st.st_size}"
    side = ocr_sidecar(p) if p.suffix.lower() == ".pdf" else None
    if side and side.is_file():   # เพิ่ม/ทำ OCR ใหม่ = ไฟล์นี้ต้อง embed ใหม่
        sig += f"_ocr{int(side.stat().st_mtime)}"
    return sig

INDEX_VER = 2   # เปลี่ยนเมื่อวิธีอ่าน/แบ่งข้อความเปลี่ยน -> cache เก่าใช้ไม่ได้ ต้อง embed ใหม่ทั้งหมด (v2: แบ่งท่อนยาว + แก้สระไทย PDF)
_build_lock = threading.Lock()

def build_index(force=False, log=print):
    # ทีละรอบเท่านั้น: เดิมรอบตอนเปิด gateway กับรอบที่สั่ง reindex ทำพร้อมกัน embed ไฟล์เดียวกันซ้ำ
    # และรอบที่จบทีหลังเขียนทับผลของอีกรอบ
    if not _build_lock.acquire(blocking=False):
        log("index: กำลังสร้างอยู่แล้ว — ข้ามคำสั่งนี้")
        return False
    try:
        return _build_index(force, log)
    finally:
        _build_lock.release()

def _build_index(force=False, log=print):
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
    cached_files = cache.get("files", {}) if cache.get("ver") == INDEX_VER else {}
    if cache and not cached_files:
        log(f"index: รูปแบบ cache เปลี่ยน (v{cache.get('ver', 1)} -> v{INDEX_VER}) — embed ใหม่ทุกไฟล์")

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
            failed = len(cks) - len(pairs)
            # embed ล้มเหลว (เช่น Ollama ปิด/กำลังอัปเดต): ไม่จำลายเซ็นไฟล์ รอบหน้าจะ embed ใหม่
            # (เดิมจำไว้ทั้งที่ได้ 0 chunks ไฟล์ไม่เปลี่ยนจึงไม่ถูก embed อีกเลย คลังความรู้ว่างถาวร)
            if failed:
                log(f"     {failed}/{len(cks)} chunks embed ไม่สำเร็จ — จะลองใหม่รอบหน้า")
            e = {"sig": "" if failed else sig, "chunks": [c for c, _ in pairs], "vecs": [v for _, v in pairs]}
            # บันทึกทุกไฟล์ที่ embed เสร็จ: ถ้าปิด gateway กลางทาง (ทั้งหมดใช้เวลานาน) รอบหน้าไม่ต้องเริ่มใหม่ทั้งหมด
            CACHE_FILE.write_text(json.dumps({"ver": INDEX_VER, "files": {**cached_files, **new_cache_files, key: e}},
                                             ensure_ascii=False), encoding="utf-8")
        new_cache_files[key] = e
        for c, v in zip(e["chunks"], e["vecs"]):
            chunks.append(c)
            vecs.append(v)
            sources.append(p.name)

    with _index_lock:
        _index.update(chunks=chunks, vecs=vecs, sources=sources,
                      indexed_at=time.strftime("%Y-%m-%d %H:%M:%S"), files=len(files))
    CACHE_FILE.write_text(json.dumps({"ver": INDEX_VER, "files": new_cache_files}, ensure_ascii=False), encoding="utf-8")
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
SAME_ORIGINS = {f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"}



def _same_origin(handler):
    # ปลายทางนี้ใช้เครดิต KKU ของผู้ใช้ -> รับเฉพาะหน้าแชทของ gateway เอง (หรือโปรแกรมในเครื่องที่ไม่มี Origin)
    origin = handler.headers.get("Origin")
    if origin and origin not in SAME_ORIGINS:
        return False
    return handler.headers.get("Sec-Fetch-Site") != "cross-site"


# ============================================================
# ศูนย์ผู้ให้บริการ (ทะเบียนกลาง F:\LocalAI\shared\providers.json จัดการใน Multi Tools) — คีย์อยู่ฝั่ง server เท่านั้น
#   GET  /api/hub/providers              รายชื่อที่เปิดใช้ + พร้อมใช้ (มีคีย์) ไหม
#   GET  /api/hub/<id>/v1/models         POST /api/hub/<id>/v1/chat/completions   (proxy ใส่คีย์ให้)
#   /api/kku/v1/* ของเดิมยังใช้ได้ (= /api/hub/kku/v1/*)
# ============================================================
HUB_FILE = os.environ.get("LUNGPEE_PROVIDERS") or r"F:\LocalAI\shared\providers.json"
HUB_PATHS = {("GET", "/v1/models"), ("POST", "/v1/chat/completions")}


def _env_key(name):
    # อ่านจาก registry สำรอง เพราะ gateway ที่เปิดก่อนตั้งตัวแปรจะไม่เห็นใน os.environ
    if not name:
        return ""
    key = os.environ.get(name)
    if key:
        return key
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0] or ""
    except OSError:
        return ""


def hub_providers():
    """รายการที่เปิดใช้ในทะเบียนกลาง — ถ้าไม่มีไฟล์ ใช้ KKU อย่างเดียวเหมือนเดิม"""
    try:
        with open(HUB_FILE, encoding="utf-8") as f:
            items = json.load(f).get("providers") or []
    except (OSError, ValueError):
        items = [{"id": "kku", "name": "KKU gen.ai (มข.)", "base": KKU_BASE, "key_env": "KKU_API_KEY"}]
    out = []
    for p in items:
        if not isinstance(p, dict) or not p.get("id") or not p.get("base") or p.get("enabled", True) is False:
            continue
        out.append({"id": p["id"], "name": p.get("name") or p["id"], "base": p["base"].rstrip("/"),
                    "key_env": p.get("key_env") or "", "auth": p.get("auth") or "bearer",
                    "models_url": p.get("models_url") or "", "models": p.get("models") or [],
                    "free": bool(p.get("free")), "paid": bool(p.get("paid"))})
    return out


def _hub_headers(p, key):
    if p["auth"] == "none":
        return {}
    if p["auth"] == "anthropic":
        return {"Authorization": "Bearer " + key, "x-api-key": key, "anthropic-version": "2023-06-01"}
    return {"Authorization": "Bearer " + key}


def hub_proxy(handler, method, sub, body=None):
    if not _same_origin(handler):
        _send_error(handler, "forbidden origin", 403); return
    if sub == "/providers":
        _send_json(handler, [{**{k: p[k] for k in ("id", "name", "free", "paid", "models")},
                              "available": p["auth"] == "none" or bool(_env_key(p["key_env"]))} for p in hub_providers()]); return
    pid, _, rest = sub.lstrip("/").partition("/")
    rest = "/" + rest
    p = next((x for x in hub_providers() if x["id"] == pid), None)
    if not p:
        _send_error(handler, "ไม่พบผู้ให้บริการนี้ในทะเบียนกลาง (จัดการใน Multi Tools)", 404); return
    key = "" if p["auth"] == "none" else _env_key(p["key_env"])
    if rest == "/status":
        _send_json(handler, {"available": p["auth"] == "none" or bool(key), "base": p["base"]}); return
    if (method, rest) not in HUB_PATHS:
        _send_error(handler, "not allowed", 404); return
    if p["auth"] != "none" and not key:
        _send_error(handler, f"ยังไม่ได้ตั้งตัวแปร {p['key_env']} ของ Windows (ตั้งได้ใน Multi Tools → ตั้งค่า)", 503); return
    url = (p["models_url"] if rest == "/v1/models" and p["models_url"] else p["base"] + rest[len("/v1"):])
    req = urllib.request.Request(url, data=body, method=method, headers={
        **_hub_headers(p, key), "Content-Type": "application/json",
        "Accept": handler.headers.get("Accept") or "*/*"})
    _stream_upstream(handler, req, p["name"])


def kku_proxy(handler, method, sub, body=None):
    hub_proxy(handler, method, "/kku" + sub, body)


def _stream_upstream(handler, req, name):
    try:
        resp = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        _send_bytes(handler, e.read(), e.headers.get("Content-Type") or "application/json", e.code); return
    except urllib.error.URLError as e:
        _send_error(handler, f"เชื่อมต่อ {name} ไม่ได้: {e.reason}", 502); return
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


# ============================================================
# IMAGE GENERATION — เรียก image_runner.py (สคริปต์เดียวกับ AI-Bridge-Launcher) ด้วย python ของเครื่อง
# ============================================================
IMAGE_DIR = Path(os.environ.get("LOCAL_IMAGE_DIR") or r"F:\LocalAI\clip_bank\img")
IMAGE_RUNNER = os.environ.get("LUNGPEE_IMAGE_RUNNER", r"F:\LocalAI\gateway\image_runner.py")
# OCR PDF สแกนในคลังความรู้ (ปุ่มในหน้า 🧠 คลังความรู้) — รัน ocr_knowledge.py ด้วย python ของเครื่อง (มี pymupdf)
OCR_SCRIPT = os.environ.get("LUNGPEE_OCR_SCRIPT", r"F:\LocalAI\gateway\ocr_knowledge.py")
OCR_ENGINES = ("typhoon", "tesseract", "kku")
_ocr_job = {"proc": None, "engine": "", "mode": "", "started": None}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_image_jobs = {}


def _image_python():
    # python ตัวที่มี torch/CUDA — ไม่ใช้ตัวแรกใน PATH เพราะ WindowsApps\python.exe อาจเป็นแค่ตัวเปิด Store
    import shutil
    for cand in (os.environ.get("LUNGPEE_IMAGE_PYTHON"),
                 os.path.expandvars(r"%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe"),
                 os.path.expandvars(r"%LOCALAPPDATA%\Python\bin\python.exe")):
        if cand and os.path.isfile(cand):
            return cand
    return shutil.which("python") or "python"


def _run_image_job(job_id, req):
    import subprocess
    job = _image_jobs[job_id]
    job["status"] = "running"
    try:
        proc = subprocess.Popen([_image_python(), IMAGE_RUNNER, json.dumps(req, ensure_ascii=False)],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=os.path.dirname(IMAGE_RUNNER),
                                env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for raw in proc.stdout:
            try:
                d = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if d.get("type") == "progress":
                job.update(stage=d.get("stage", ""), frac=d.get("frac", 0))
            elif d.get("type") == "result":   # ใส่ seconds พร้อม status เพราะหน้าแชทอาจถามผลก่อนโปรเซสจบ
                job.update(seconds=round(time.time() - job["started"], 1), result=d, frac=1.0, stage="เสร็จ")
                job["status"] = "done"
            elif d.get("type") == "error":
                job.update(seconds=round(time.time() - job["started"], 1), error=d.get("message", ""))
                job["status"] = "error"
        proc.wait()
        if job["status"] == "running":
            job.update(status="error", error=f"ตัวสร้างภาพหยุดทำงาน (exit {proc.returncode})")
    except Exception as e:
        job.update(status="error", error=str(e))
    job.setdefault("seconds", round(time.time() - job["started"], 1))
    print(time.strftime("%Y-%m-%d %H:%M:%S"), "image job", job_id, job["status"], job.get("seconds"), "s")


def start_image_job(req):
    job_id = hashlib.md5(f"{time.time()}{req}".encode()).hexdigest()[:12]
    _image_jobs[job_id] = {"id": job_id, "status": "queued", "stage": "เริ่มงาน", "frac": 0.0,
                           "started": time.time(), "prompt": req.get("prompt", "")}
    for old in sorted(_image_jobs, key=lambda k: _image_jobs[k]["started"])[:-50]:
        _image_jobs.pop(old, None)
    threading.Thread(target=_run_image_job, args=(job_id, req), daemon=True).start()
    return job_id


def _ocr_log():
    return KNOWLEDGE_DIR / ".ocr" / "ocr.log"


def start_ocr(engine, mode="run", force=False):
    """mode: run = OCR หน้าที่ยังไม่มีผล / check = แค่นับหน้าที่ต้อง OCR — ทีละงานเท่านั้น"""
    import subprocess
    if _ocr_job["proc"] and _ocr_job["proc"].poll() is None:
        raise RuntimeError("กำลังทำ OCR อยู่แล้ว รอให้เสร็จก่อน")
    if not os.path.isfile(OCR_SCRIPT):
        raise RuntimeError(f"ไม่พบ {OCR_SCRIPT}")
    engine = engine if engine in OCR_ENGINES else "typhoon"
    args = [_image_python(), "-u", OCR_SCRIPT, "--engine", engine] + (["--check"] if mode == "check" else []) + (["--force"] if force else [])
    log = _ocr_log(); log.parent.mkdir(parents=True, exist_ok=True)
    out = open(log, "w", encoding="utf-8")
    _ocr_job.update(proc=subprocess.Popen(args, stdout=out, stderr=subprocess.STDOUT, cwd=os.path.dirname(OCR_SCRIPT),
                                          env=dict(os.environ, PYTHONIOENCODING="utf-8", LUNGPEE_KNOWLEDGE=str(KNOWLEDGE_DIR)),
                                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)),
                    engine=engine, mode=mode, started=time.time())
    return ocr_status()


def ocr_status():
    proc = _ocr_job["proc"]
    running = bool(proc and proc.poll() is None)
    try:
        lines = _ocr_log().read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
    except OSError:
        lines = []
    return {"running": running, "engine": _ocr_job["engine"], "mode": _ocr_job["mode"],
            "seconds": round(time.time() - _ocr_job["started"]) if _ocr_job["started"] else 0,
            "exit": None if running or not proc else proc.returncode, "log": lines}


def list_images(limit=24):
    files = [p for p in IMAGE_DIR.glob("*") if p.suffix.lower() in IMAGE_EXTS]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "mtime": int(p.stat().st_mtime)} for p in files[:limit]]


def serve_image(handler, name):
    p = IMAGE_DIR / os.path.basename(name or "")   # basename: กันการขอไฟล์นอกโฟลเดอร์ภาพ
    if p.suffix.lower() not in IMAGE_EXTS or not p.is_file():
        _send_error(handler, "not found", 404); return
    ctype = {".png": "image/png", ".webp": "image/webp"}.get(p.suffix.lower(), "image/jpeg")
    _send_bytes(handler, p.read_bytes(), ctype)


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
            if u.path.startswith("/api/hub/"):
                hub_proxy(self, "GET", u.path[len("/api/hub"):])

            elif u.path.startswith("/api/kku/"):
                kku_proxy(self, "GET", u.path[len("/api/kku"):])

            elif u.path == "/api/version":
                _send_json(self, version_info())

            elif u.path == "/api/image/job":
                job = _image_jobs.get((q.get("id") or [""])[0])
                _send_json(self, job) if job else _send_error(self, "unknown job", 404)

            elif u.path == "/api/image/file":
                serve_image(self, (q.get("name") or [""])[0])

            elif u.path == "/api/image/list":
                _send_json(self, {"dir": str(IMAGE_DIR), "images": list_images(int((q.get("limit") or ["24"])[0]))})

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
            elif u.path == "/api/rag/ocr/status":
                _send_json(self, ocr_status())

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
            if u.path.startswith("/api/hub/"):
                hub_proxy(self, "POST", u.path[len("/api/hub"):], json.dumps(data).encode("utf-8"))

            elif u.path.startswith("/api/kku/"):
                kku_proxy(self, "POST", u.path[len("/api/kku"):], json.dumps(data).encode("utf-8"))

            elif u.path == "/api/rag/ocr":
                # ใช้ GPU/เครดิตของผู้ใช้ -> รับเฉพาะหน้าแชทของ gateway เอง
                if not _same_origin(self):
                    _send_error(self, "forbidden origin", 403)
                else:
                    try:
                        _send_json(self, start_ocr(data.get("engine", "typhoon"), data.get("mode", "run"), bool(data.get("force"))))
                    except RuntimeError as e:
                        _send_error(self, str(e), 409)

            elif u.path == "/api/image":
                # ใช้ GPU/เครดิตของผู้ใช้ -> รับเฉพาะหน้าแชทของ gateway เอง
                if not _same_origin(self):
                    _send_error(self, "forbidden origin", 403)
                elif not (data.get("prompt") or "").strip():
                    _send_error(self, "missing prompt", 400)
                else:
                    _send_json(self, {"id": start_image_job(data)})

            elif u.path == "/api/shutdown":
                # ปุ่ม "ออกจากโปรแกรม" ในหน้าแชท — รับเฉพาะหน้าของ gateway เอง กันเว็บอื่นสั่งปิด
                if not _same_origin(self):
                    _send_error(self, "forbidden origin", 403)
                else:
                    _send_json(self, {"ok": True})
                    print(time.strftime("%Y-%m-%d %H:%M:%S"), "shutdown requested from chat UI")
                    threading.Thread(target=self.server.shutdown, daemon=True).start()

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
                busy = _build_lock.locked()
                force = data.get("force", True) is not False   # {"force": false} = embed เฉพาะไฟล์ที่เปลี่ยน (เช่น หลังทำ OCR)
                if not busy:
                    threading.Thread(target=lambda: build_index(force=force), daemon=True).start()
                _send_json(self, {"ok": True, "msg": "already indexing" if busy else "reindexing..."})
            
            else:
                _send_error(self, "not found", 404)
        
        except Exception as e:
            _send_error(self, f"POST error: {e}")

# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print(time.strftime("%Y-%m-%d %H:%M:%S"), about_text())
    print(f"LocalAI Unified Gateway on http://{HOST}:{PORT}")
    print("Endpoints:")
    print("  /api/kku/v1/* -> KKU gen.ai (key from KKU_API_KEY)")
    print("  /api/hub/providers, /api/hub/<id>/v1/* -> providers from F:\\LocalAI\\shared\\providers.json (keys from Windows env)")
    print("  /api/version, /api/shutdown -> version info / exit (same-origin only)")
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