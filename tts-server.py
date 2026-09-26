#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LocalAI TTS server - Microsoft Edge Neural voices (free, no API key)
Serves Thai neural voices Premwadee (female) / Niwat (male) to chat.html.
Needs internet. Runs on 127.0.0.1:11435.

Endpoints:
  GET /health                              -> "ok"
  GET /voices                              -> JSON list of th-TH voices
  GET /tts?text=...&voice=...&rate=+0%     -> audio/mpeg (mp3)
"""
import asyncio
import json
import os
from urllib.parse import urlparse, parse_qs, unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import edge_tts

HOST, PORT = "127.0.0.1", 11435
DEFAULT_VOICE = "th-TH-PremwadeeNeural"

# เสิร์ฟหน้า UI ผ่าน http://localhost เพื่อให้ไมโครโฟน/Web Speech ทำงาน (file:// บล็อก)
BASE = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE, "ui")
MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml", ".gif": "image/gif",
        ".ico": "image/x-icon", ".woff2": "font/woff2", ".map": "application/json"}

async def synth(text, voice, rate):
    audio = bytearray()
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return bytes(audio)

async def list_thai_voices():
    voices = await edge_tts.list_voices()
    return [
        {"name": v["ShortName"], "gender": v.get("Gender", ""), "locale": v.get("Locale", "")}
        for v in voices if v.get("Locale", "").startswith("th")
    ]

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # quiet

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else ""
            data = json.loads(body) if body else {}
            if u.path == "/tts":
                text = (data.get("text") or "").strip()
                voice = data.get("voice") or DEFAULT_VOICE
                rate = data.get("rate") or "+0%"
                if not text:
                    self._send(400, b"missing text", "text/plain")
                    return
                audio = asyncio.run(synth(text, voice, rate))
                self._send(200, audio, "audio/mpeg")
            elif u.path == "/clip":
                self._make_clip(data)
            elif u.path == "/config":
                self._config_save(data)
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:
            self._send(500, ("error: " + str(e)).encode("utf-8"), "text/plain; charset=utf-8")

    def _make_clip(self, data):
        import time
        scenes = data.get("scenes") or []
        if not scenes:
            self._send(400, "ไม่มีฉาก (scenes)".encode("utf-8"), "text/plain; charset=utf-8")
            return
        try:
            import clipgen, importlib
            importlib.reload(clipgen)  # โหลดโค้ดล่าสุดทุกครั้ง (แก้ clipgen.py แล้วไม่ต้องรีสตาร์ท)
        except Exception as e:
            self._send(500, ("โหลด clipgen ไม่ได้: " + str(e)).encode("utf-8"), "text/plain; charset=utf-8")
            return
        ffmpeg = os.path.join(BASE, "tools", "ffmpeg", "ffmpeg.exe")
        if not os.path.isfile(ffmpeg):
            ffmpeg = "ffmpeg"
        workdir = os.path.join(BASE, "clips", "_work")
        out = os.path.join(BASE, "clips", "gen_%d.mp4" % int(time.time()))
        voice = data.get("voice") or DEFAULT_VOICE
        fmt = data.get("format") or "portrait"
        subtitle = data.get("subtitle", True)
        music = data.get("music")
        if music == "default":
            music = os.path.join(BASE, "tools", "music", "ambient.mp3")
        clipgen.make_clip(scenes[:12], voice, ffmpeg, workdir, out, fmt=fmt,
                          subtitle=subtitle, music=music)
        with open(out, "rb") as f:
            body = f.read()
        self._send(200, body, "video/mp4")

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/health":
                self._send(200, b"ok", "text/plain")
            elif u.path == "/voices":
                data = asyncio.run(list_thai_voices())
                self._send(200, json.dumps(data).encode("utf-8"), "application/json")
            elif u.path == "/tts":
                text = unquote(q.get("text", [""])[0])
                voice = q.get("voice", [DEFAULT_VOICE])[0]
                rate = q.get("rate", ["+0%"])[0]
                if not text.strip():
                    self._send(400, b"missing text", "text/plain")
                    return
                audio = asyncio.run(synth(text, voice, rate))
                self._send(200, audio, "audio/mpeg")
            elif u.path == "/file":
                self._send_file_content(unquote(q.get("path", [""])[0]))
            elif u.path == "/proxy":
                self._proxy_fetch(unquote(q.get("url", [""])[0]))
            elif u.path == "/config":
                self._config_load()
            else:
                self._serve_static(u.path)
        except Exception as e:
            self._send(500, ("TTS error: " + str(e)).encode("utf-8"), "text/plain")

    def _config_path(self):
        return os.path.join(BASE, "model.md")

    def _config_load(self):
        """GET /config -> คืน JSON ที่ฝังใน model.md"""
        import re
        path = self._config_path()
        if not os.path.isfile(path):
            self._send(404, b'{"error":"no saved config"}', "application/json; charset=utf-8")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            m = re.search(r"```json\s*\n([\s\S]*?)\n```", content)
            if not m:
                self._send(500, b'{"error":"no JSON block in model.md"}', "application/json; charset=utf-8")
                return
            self._send(200, m.group(1).encode("utf-8"), "application/json; charset=utf-8")
        except Exception as e:
            self._send(500, ('{"error":"' + str(e).replace('"', "'") + '"}').encode("utf-8"),
                       "application/json; charset=utf-8")

    def _config_save(self, cfg):
        """POST /config {cfg:{...}} -> เขียนเป็น markdown อ่านได้ + JSON block ลง model.md"""
        import time
        try:
            data = cfg.get("cfg") if isinstance(cfg, dict) and "cfg" in cfg else cfg
            if not isinstance(data, dict):
                self._send(400, b'{"error":"cfg must be object"}', "application/json; charset=utf-8")
                return
            # Build human-readable markdown
            lines = []
            lines.append("# LocalAI Config Backup")
            lines.append("")
            lines.append("> ⚠️ ไฟล์นี้เก็บ API keys เป็น plaintext — อย่าอัปโหลด/แชร์")
            lines.append("> อัปเดตอัตโนมัติทุกครั้งที่แก้ Settings ใน chat.html")
            lines.append("")
            lines.append("อัปเดต: " + time.strftime("%Y-%m-%d %H:%M:%S"))
            lines.append("")
            lines.append("## Providers (" + str(len(data.get("providers") or [])) + " ราย)")
            lines.append("")
            for i, p in enumerate(data.get("providers") or [], 1):
                lines.append("### " + str(i) + ". " + (p.get("label") or "-"))
                lines.append("- **Base URL:** " + (p.get("baseUrl") or "-"))
                key = p.get("apiKey") or ""
                masked = (key[:8] + "…" + key[-4:]) if len(key) > 16 else ("(set)" if key else "(empty)")
                lines.append("- **API Key:** `" + masked + "` (full ในบล็อก JSON ด้านล่าง)")
                models = p.get("models") or []
                if isinstance(models, list):
                    lines.append("- **Models (" + str(len(models)) + "):** " + ", ".join(models[:20]) +
                                 (" …" if len(models) > 20 else ""))
                else:
                    lines.append("- **Models:** " + str(models))
                lines.append("")
            lines.append("## Settings")
            lines.append("")
            lines.append("| Key | Value |")
            lines.append("|-----|-------|")
            for k in ("system", "ctx", "temp", "topK", "ragOn", "ttsEngine", "neuralVoice",
                      "voiceRate", "ttsUrl", "ollamaUrl", "freeOnline", "autoFallback"):
                v = data.get(k)
                if v is None:
                    continue
                sv = str(v)
                if len(sv) > 80:
                    sv = sv[:80] + "…"
                lines.append("| " + k + " | " + sv.replace("|", "\\|").replace("\n", " ") + " |")
            lines.append("")
            lines.append("## Raw JSON (ระบบใช้บล็อกนี้ตอน restore)")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(data, ensure_ascii=False, indent=2))
            lines.append("```")
            content = "\n".join(lines) + "\n"
            with open(self._config_path(), "w", encoding="utf-8") as f:
                f.write(content)
            self._send(200, b'{"ok":true,"path":"' + self._config_path().replace("\\", "/").encode("utf-8") + b'"}',
                       "application/json; charset=utf-8")
        except Exception as e:
            self._send(500, ('{"error":"' + str(e).replace('"', "'") + '"}').encode("utf-8"),
                       "application/json; charset=utf-8")

    def _proxy_fetch(self, url):
        """ดึงเนื้อหาบทความจาก URL (bypass CORS) -> คืนเป็นข้อความล้วน
        - ตาม redirect (Google News, hnrss)
        - แปลง HTML -> plain text (คงย่อหน้า)
        - จำกัดขนาด 200KB (ประมาณ 40k chars)
        """
        import re, urllib.request, urllib.error, gzip, io
        if not url or not url.startswith(("http://", "https://")):
            self._send(400, "missing or invalid url".encode("utf-8"), "text/plain; charset=utf-8")
            return
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "th,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                final_url = resp.geturl()
                raw = resp.read(200 * 1024)  # 200KB
                enc = resp.headers.get("Content-Encoding", "")
                if enc == "gzip":
                    raw = gzip.decompress(raw)
                elif enc == "deflate":
                    import zlib
                    raw = zlib.decompress(raw)
                # decode
                ctype = resp.headers.get("Content-Type", "")
                m = re.search(r"charset=([\w-]+)", ctype)
                charset = m.group(1) if m else "utf-8"
                try:
                    html = raw.decode(charset, "replace")
                except Exception:
                    html = raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            self._send(502, ("HTTP %d: %s" % (e.code, e.reason)).encode("utf-8"), "text/plain; charset=utf-8")
            return
        except Exception as e:
            self._send(502, ("fetch failed: " + str(e)).encode("utf-8"), "text/plain; charset=utf-8")
            return
        # HTML -> text
        # ตัด script/style/nav/aside/footer/header/svg
        html = re.sub(r"(?is)<(script|style|nav|aside|footer|header|svg|form|noscript|iframe)[^>]*>.*?</\1>", " ", html)
        # ดึง title + meta description
        title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
        desc_m = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', html)
        og_m = re.search(r'(?is)<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']', html)
        title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""
        desc = (desc_m.group(1) if desc_m else (og_m.group(1) if og_m else "")).strip()
        # ดึงเฉพาะ <article> / <main> ถ้ามี — คุณภาพดีกว่า
        article_m = re.search(r"(?is)<article[^>]*>(.*?)</article>", html)
        main_m = re.search(r"(?is)<main[^>]*>(.*?)</main>", html)
        body = article_m.group(1) if article_m else (main_m.group(1) if main_m else html)
        # แทน <br>, <p>, <li>, <h*>, <div> ด้วย \n เพื่อคงย่อหน้า
        body = re.sub(r"(?is)<(br|hr)\s*/?>", "\n", body)
        body = re.sub(r"(?is)</(p|div|li|h[1-6]|section|article|blockquote|tr)>", "\n", body)
        body = re.sub(r"(?is)<li[^>]*>", "\n• ", body)
        # ตัด tag ทั้งหมด
        text = re.sub(r"(?s)<[^>]+>", " ", body)
        # decode entities
        html_entities = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
                         "&quot;": '"', "&#39;": "'", "&apos;": "'", "&mdash;": "—",
                         "&ndash;": "–", "&hellip;": "…", "&laquo;": "«", "&raquo;": "»",
                         "&ldquo;": '"', "&rdquo;": '"', "&lsquo;": "'", "&rsquo;": "'"}
        for k, v in html_entities.items():
            text = text.replace(k, v)
        text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
        text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
        # ล้าง whitespace: หลายๆ ช่องว่างในบรรทัด -> 1 ช่องว่าง, หลาย \n -> 2 \n
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n[ \t]*", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()
        # ต่อ header
        header = ""
        if title:
            header += "หัวข้อ: " + title + "\n"
        if desc and desc not in text[:500]:
            header += "คำโปรย: " + desc + "\n"
        header += "URL: " + final_url + "\n\n"
        # จำกัดขนาดสุดท้าย ~15000 chars (พอสำหรับ context 4096-8192 tokens)
        MAX = 15000
        if len(text) > MAX:
            text = text[:MAX] + "\n\n[…ตัดที่ %d chars…]" % MAX
        self._send(200, (header + text).encode("utf-8"), "text/plain; charset=utf-8")

    def _send_file_content(self, path):
        # อ่านไฟล์/โฟลเดอร์ในเครื่องตาม path -> ส่งกลับเป็นข้อความ
        if not path:
            self._send(400, "missing path".encode("utf-8"), "text/plain; charset=utf-8")
            return
        if os.path.isdir(path):
            entries = []
            for name in sorted(os.listdir(path)):
                fp = os.path.join(path, name)
                kind = "โฟลเดอร์" if os.path.isdir(fp) else (str(os.path.getsize(fp)) + " bytes")
                entries.append(name + "  (" + kind + ")")
            text = "[โฟลเดอร์: %s]\n" % path + "\n".join(entries)
            self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")
            return
        if not os.path.isfile(path):
            self._send(404, ("ไม่พบไฟล์: " + path).encode("utf-8"), "text/plain; charset=utf-8")
            return
        size = os.path.getsize(path)
        if size > 5 * 1024 * 1024:
            self._send(413, ("ไฟล์ใหญ่เกิน 5MB (" + str(size) + " bytes)").encode("utf-8"), "text/plain; charset=utf-8")
            return
        ext = os.path.splitext(path)[1].lower()
        if ext == ".xlsx":
            text = self._xlsx_to_text(path)
        else:
            with open(path, "rb") as f:
                raw = f.read()
            text = None
            for enc in ("utf-8-sig", "utf-8", "cp874", "tis-620", "latin-1"):
                try:
                    text = raw.decode(enc); break
                except Exception:
                    continue
            if text is None:
                text = raw.decode("latin-1", "replace")
            # ไฟล์ .xls ของ AMR เป็น HTML table -> แปลงเป็นตารางอ่านง่าย
            if "<table" in text.lower() or "<tr" in text.lower():
                text = self._html_table_to_text(text)
        self._send(200, text.encode("utf-8"), "text/plain; charset=utf-8")

    def _html_table_to_text(self, html):
        import re
        html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
        rows = re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html)
        out = []
        for r in rows:
            cells = re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", r)
            cells = [re.sub(r"(?s)<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in cells]
            if any(cells):
                out.append(" | ".join(cells))
        return "\n".join(out) if out else re.sub(r"(?s)<[^>]+>", " ", html)

    def _xlsx_to_text(self, path):
        try:
            import openpyxl
        except ImportError:
            return "(อ่าน .xlsx ไม่ได้ - ติดตั้ง openpyxl ก่อน: python -m pip install openpyxl)"
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        out = []
        for ws in wb.worksheets:
            out.append("[ชีท: %s]" % ws.title)
            for row in ws.iter_rows(values_only=True):
                out.append(",".join("" if c is None else str(c) for c in row))
        return "\n".join(out)

    def _serve_static(self, path):
        # เสิร์ฟไฟล์ในโฟลเดอร์ ui/ (chat.html, lib/*) ป้องกัน path traversal
        rel = unquote(path.lstrip("/")) or "chat.html"
        if rel in ("", "/"):
            rel = "chat.html"
        full = os.path.normpath(os.path.join(UI_DIR, rel))
        if not full.startswith(UI_DIR) or not os.path.isfile(full):
            self._send(404, b"not found", "text/plain")
            return
        ctype = MIME.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    print("LocalAI TTS server (Edge Neural) on http://%s:%d" % (HOST, PORT))
    print("Default voice:", DEFAULT_VOICE, "- needs internet")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
