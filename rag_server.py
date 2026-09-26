# -*- coding: utf-8 -*-
"""
rag_server.py — RAG backend สำหรับ chat.html (แก้ปัญหา browser อ่านโฟลเดอร์ไม่ได้)
- auto-index F:\LocalAI\knowledge\ (md/txt/pdf/csv) ตอนเปิด
- cache เวกเตอร์ลงดิสก์ (embed ซ้ำเฉพาะไฟล์ที่เปลี่ยน)
- embed ผ่าน Ollama bge-m3 · serve HTTP API ให้ chat.html เรียก
Endpoints (CORS เปิด):
  GET  /kb/status              -> {chunks, files, indexed_at}
  GET  /kb/search?q=..&k=4     -> {hits:[{text,source,score}]}
  POST /kb/reindex             -> rebuild ทั้งหมด
"""
import os, re, sys, json, time, hashlib, urllib.request, urllib.parse, threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass

HERE = Path(__file__).parent
KNOWLEDGE = HERE / "knowledge"
CACHE = KNOWLEDGE / ".rag_cache.json"
OLLAMA = "http://localhost:11434"
EMBED_MODEL = "bge-m3:latest"
PORT = 5002
EXTS = {".md", ".txt", ".csv", ".log", ".json"}   # + .pdf (ผ่าน pypdf ถ้ามี)

_index = {"chunks": [], "vecs": [], "sources": [], "indexed_at": None, "files": 0}
_lock = threading.Lock()

# ---------- PDF ----------
def read_pdf(path):
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
    except Exception as e:
        print(f"  PDF อ่านไม่ได้ {path.name}: {e}")
        return ""

def read_file(path):
    if path.suffix.lower() == ".pdf":
        return read_pdf(path)
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""

# ---------- chunk (มี overlap) ----------
def chunk_text(t, size=800, overlap=120):
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 > size and cur:
            chunks.append(cur)
            cur = (cur[-overlap:] + "\n\n" + p) if overlap else p   # overlap ต่อชิ้น
        else:
            cur = cur + "\n\n" + p if cur else p
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) > 40] or ([t[:size]] if t.strip() else [])

# ---------- embed via Ollama ----------
def embed(text):
    # num_gpu:0 บังคับรันบน CPU กัน bge-m3 แย่งที่โมเดลแชทใน VRAM (การ์ด 4GB ใส่พร้อมกันไม่พอ ทำให้ Ollama evict สลับไปมา)
    req = urllib.request.Request(OLLAMA + "/api/embeddings",
        data=json.dumps({"model": EMBED_MODEL, "prompt": text, "options": {"num_gpu": 0}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["embedding"]

def cosine(a, b):
    d = sum(x*y for x, y in zip(a, b))
    na = sum(x*x for x in a) ** 0.5; nb = sum(y*y for y in b) ** 0.5
    return d/(na*nb) if na and nb else 0.0

def file_sig(p):
    st = p.stat()
    return f"{int(st.st_mtime)}_{st.st_size}"

# ---------- index (ใช้ cache) ----------
def build_index(force=False, log=print):
    KNOWLEDGE.mkdir(exist_ok=True)
    files = [p for p in KNOWLEDGE.rglob("*")
             if p.is_file() and not p.name.startswith(".")
             and (p.suffix.lower() in EXTS or p.suffix.lower() == ".pdf")
             # ข้ามโฟลเดอร์ซ่อน/โปรเจกต์อื่น (.claude ฯลฯ)
             and not any(part.startswith(".") for part in p.relative_to(KNOWLEDGE).parts[:-1])]
    # โหลด cache
    cache = {}
    if CACHE.exists() and not force:
        try: cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception: cache = {}
    cached_files = cache.get("files", {})

    chunks, vecs, sources = [], [], []
    new_cache_files = {}
    for p in files:
        sig = file_sig(p); key = str(p)
        if key in cached_files and cached_files[key]["sig"] == sig:
            e = cached_files[key]                      # ใช้ cache เดิม (ไม่ embed ซ้ำ)
            log(f"  ✓ cache: {p.name} ({len(e['chunks'])} chunks)")
        else:
            text = read_file(p)
            cks = chunk_text(text)
            log(f"  🔢 embed: {p.name} ({len(cks)} chunks)...")
            cvs = []
            for ci, c in enumerate(cks, 1):
                try: cvs.append(embed(c))
                except Exception as ex: log(f"     embed fail: {ex}"); cvs.append(None)
                log(f"     ...{ci}/{len(cks)}"); sys.stdout.flush()
            pairs = [(c, v) for c, v in zip(cks, cvs) if v]
            e = {"sig": sig, "chunks": [c for c, _ in pairs], "vecs": [v for _, v in pairs]}
        new_cache_files[key] = e
        for c, v in zip(e["chunks"], e["vecs"]):
            chunks.append(c); vecs.append(v); sources.append(p.name)

    with _lock:
        _index.update(chunks=chunks, vecs=vecs, sources=sources,
                      indexed_at=time.strftime("%Y-%m-%d %H:%M:%S"), files=len(files))
    CACHE.write_text(json.dumps({"files": new_cache_files}, ensure_ascii=False), encoding="utf-8")
    log(f"✅ index เสร็จ: {len(chunks)} chunks จาก {len(files)} ไฟล์")

def search(q, k=4):
    qv = embed(q)
    with _lock:
        scored = sorted(
            ({"text": c, "source": s, "score": cosine(qv, v)}
             for c, v, s in zip(_index["chunks"], _index["vecs"], _index["sources"])),
            key=lambda x: -x["score"])
    return scored[:k]

# ---------- HTTP ----------
class H(BaseHTTPRequestHandler):
    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)
    def do_OPTIONS(self): self._send({})
    def log_message(self, *a): pass
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/kb/status":
            self._send({"chunks": len(_index["chunks"]), "files": _index["files"],
                        "indexed_at": _index["indexed_at"]})
        elif u.path == "/kb/search":
            qs = urllib.parse.parse_qs(u.query)
            q = (qs.get("q") or [""])[0]; k = int((qs.get("k") or ["4"])[0])
            if not q: self._send({"hits": []}); return
            try: self._send({"hits": search(q, k)})
            except Exception as e: self._send({"error": str(e)}, 500)
        else:
            self._send({"error": "not found"}, 404)
    def do_POST(self):
        if self.path == "/kb/reindex":
            threading.Thread(target=lambda: build_index(force=True), daemon=True).start()
            self._send({"ok": True, "msg": "reindexing..."})
        else:
            self._send({"error": "not found"}, 404)

if __name__ == "__main__":
    print(f"RAG server · knowledge: {KNOWLEDGE}")
    print("กำลัง index ครั้งแรก...")
    build_index()
    print(f"🚀 serve http://localhost:{PORT}  (/kb/status /kb/search /kb/reindex)")
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
