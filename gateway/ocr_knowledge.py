# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

# -*- coding: utf-8 -*-
"""ocr_knowledge.py — อ่านตัวอักษรจากภาพ (OCR) ให้ PDF ในคลังความรู้ของ ลุงพี AI โดย ลุงพี

ทำเฉพาะหน้าที่ต้องใช้: หน้าภาพสแกน (ไม่มีข้อความในไฟล์) และหน้าที่ถอดข้อความออกมาเป็นอักษรเพี้ยน
(ฟอนต์ไทยรุ่นเก่า เช่น AngsanaUPC ที่ไม่มีตาราง Unicode) — หน้าที่อ่านได้อยู่แล้วไม่แตะ
ผลเก็บที่ knowledge\\.ocr\\<path>.pdf.json แล้ว gateway ใช้ข้อความนี้แทนเฉพาะหน้านั้น

    python ocr_knowledge.py                      ทำทุกไฟล์ที่ยังไม่มีผล OCR ด้วย Typhoon OCR (ค่าเริ่มต้น)
    python ocr_knowledge.py --engine tesseract   ใช้ Tesseract (เร็ว แต่สระ/ตัวเลขไทยพลาดบ่อยกว่า)
    python ocr_knowledge.py --engine kku         ใช้โมเดลออนไลน์ของ KKU gen.ai (ใช้เครดิต)
    python ocr_knowledge.py --force FiTv         ทำใหม่ทั้งที่มีผลแล้ว เฉพาะไฟล์ที่ชื่อมีคำว่า FiTv
    python ocr_knowledge.py --check              แค่แสดงว่าไฟล์ไหนมีกี่หน้าที่ต้อง OCR
    python ocr_knowledge.py --clean              ตัดคำบรรยายรูปออกจากผล OCR ที่มีอยู่ (ไม่ต้อง OCR ใหม่)

ใช้จากหน้าจอได้: ลุงพี AI -> 🧠 คลังความรู้ -> ปุ่ม "🔍 OCR PDF สแกน" (เลือกตัวอ่านได้ ดูความคืบหน้าในหน้าต่างเดียวกัน)

เสร็จแล้วสั่ง gateway จัดคลังเฉพาะไฟล์ที่เปลี่ยน ({"force": false}) ไม่ต้อง embed ใหม่ทั้งหมด
"""
import argparse
import base64
import html
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

KNOWLEDGE = Path(os.environ.get("LUNGPEE_KNOWLEDGE", r"C:\Users\Lenovo\LungPeeAI\_internal\knowledge"))
GATEWAY = "http://127.0.0.1:11435"
OLLAMA = "http://127.0.0.1:11434"
TYPHOON_MODEL = "scb10x/typhoon-ocr1.5-3b"
TESSERACT = Path(os.environ.get("TESSERACT_EXE", r"C:\Program Files\Tesseract-OCR\tesseract.exe"))
TESSDATA = Path(os.environ.get("TESSDATA_DIR", r"F:\LocalAI\models\tessdata"))   # tha + eng + osd (Program Files เขียนไม่ได้ถ้าไม่ใช่ admin)
KKU_BASE = "https://gen.ai.kku.ac.th/okmd/api/v1"
KKU_MODEL = "gpt-5.4-mini"

# prompt ของ Typhoon OCR v1.5 (model card ระบุว่าใช้ได้กับ prompt นี้เท่านั้น)
TYPHOON_PROMPT = """Extract all text from the image.

Instructions:
- Only return the clean Markdown.
- Do not include any explanation or extra text.
- You must include all information on the page.

Formatting Rules:
- Tables: Render tables using <table>...</table> in clean HTML format.
- Equations: Render equations using LaTeX syntax with inline ($...$) and block ($$...$$).
- Images/Charts/Diagrams: Wrap any clearly defined visual areas (e.g. charts, diagrams, pictures) in:

<figure>
Describe the image's main elements (people, objects, text), note any contextual clues (place, event, culture), mention visible text and its meaning, provide deeper analysis when relevant (especially for financial charts, graphs, or documents), comment on style or architecture if relevant, then give a concise overall summary. Describe in Thai.
</figure>

- Page Numbers: Wrap page numbers in <page_number>...</page_number> (e.g., <page_number>14</page_number>).
- Checkboxes: Use ☐ for unchecked and ☑ for checked boxes."""
KKU_PROMPT = ("ถอดข้อความทั้งหมดในภาพหน้าเอกสารนี้ให้ตรงตามต้นฉบับทุกตัวอักษร (ไทยและอังกฤษ) "
              "ตารางให้เขียนทีละแถว คั่นช่องด้วย | ตอบเฉพาะข้อความที่ถอดได้")


def needs_ocr(text):
    """หน้าไม่มีข้อความ หรือเป็นอักษร Latin-1 ปนมากเกิน 20% ของตัวอักษรไทย+Latin-1 (ฟอนต์ไทยรุ่นเก่าถอดเพี้ยน)"""
    t = (text or "").strip()
    if len(t) < 30:
        return True
    latin1 = len(re.findall(r"[\u00a1-\u00ff]", t))
    thai = len(re.findall(r"[\u0e00-\u0e7f]", t))
    return latin1 > 20 and latin1 / (latin1 + thai) > 0.2


def file_sig(p):
    st = p.stat()
    return f"{int(st.st_mtime)}_{st.st_size}"   # ต้องตรงกับที่ gateway ใช้ตรวจว่า PDF ไม่เปลี่ยนหลังทำ OCR


def sidecar(p):
    return KNOWLEDGE / ".ocr" / (str(p.relative_to(KNOWLEDGE)) + ".json")


FIGURE_RE = re.compile(r"<figure\b.*?(?:</figure>|$)", re.S | re.I)
# คำบรรยายรูปที่ OCR รุ่นก่อนเก็บไว้แล้ว (แท็ก <figure> ถูกตัดไปแล้ว): ย่อหน้าที่โมเดลแต่งขึ้นเอง ขึ้นต้นแบบนี้และยาว
FIGURE_PARA_RE = re.compile(r"^\s*(ภาพ(?!ที่)|รูป(?!ที่)|แผนภาพ|แผนภูมิ|กราฟ|ตราสัญลักษณ์|โลโก้)")


def strip_figure_paragraphs(text):
    paras = re.split(r"\n\s*\n", text)
    keep = [p for p in paras if not (FIGURE_PARA_RE.match(p) and len(p.strip()) > 60)]
    return "\n\n".join(keep).strip()


def tidy(text):
    """HTML ตารางจาก Typhoon -> แถวข้อความ "a | b" (ค้นหาง่ายกว่า) ตัดคำบรรยายรูป <figure> ที่โมเดลแต่งเพิ่ม
    (ไม่ใช่ข้อความในเอกสาร ทำให้ผลค้นมีข้อความเช่น "ภาพตราสัญลักษณ์ของ กฟภ. ..." ติดมา) และแท็กที่ไม่ใช่เนื้อหา"""
    t = FIGURE_RE.sub(" ", text)
    t = re.sub(r"</t[dh]>\s*<t[dh][^>]*>", " | ", t, flags=re.I)
    t = re.sub(r"</?(tr|table|thead|tbody)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"</?(t[dh]|page_number|figure|br)[^>]*>", " ", t, flags=re.I)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", t).strip()


def page_image(page, longest=1800, fmt="png", gray=False):
    import pymupdf
    zoom = longest / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), colorspace=pymupdf.csGRAY if gray else pymupdf.csRGB)
    if fmt == "png":
        return pix.tobytes("png")
    from PIL import Image
    img = Image.frombytes("L" if gray else "RGB", (pix.width, pix.height), pix.samples)
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=70)
    return buf.getvalue()


def _post(url, body, headers=None, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def ocr_typhoon(page):
    img = base64.b64encode(page_image(page, 1800, "png")).decode()   # โมเดลฝึกที่ด้านยาว 1800 px
    d = _post(OLLAMA + "/api/chat", {
        "model": TYPHOON_MODEL, "stream": False, "keep_alive": "10m",
        "messages": [{"role": "user", "content": TYPHOON_PROMPT, "images": [img]}],
        "options": {"temperature": 0.1, "repeat_penalty": 1.1, "num_ctx": 12288, "num_predict": 6000},
    })
    if d.get("error"):
        raise RuntimeError(d["error"])
    return d["message"]["content"]


def ocr_tesseract(page):
    if not TESSERACT.is_file():
        raise RuntimeError(f"ไม่พบ Tesseract ที่ {TESSERACT}")
    png = page_image(page, 3000, "png", gray=True)   # ~300 dpi สำหรับ A4
    r = subprocess.run([str(TESSERACT), "stdin", "stdout", "--tessdata-dir", str(TESSDATA), "-l", "tha+eng", "--psm", "6"],
                       input=png, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[:300])
    return r.stdout.decode("utf-8", "replace")


def _kku_key():
    key = os.environ.get("KKU_API_KEY")
    if not key:
        import winreg
        key = winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment"), "KKU_API_KEY")[0]
    return key


def ocr_kku(page):
    jpg = base64.b64encode(page_image(page, 1754, "jpg", gray=True)).decode()   # KKU รับคำขอขนาดจำกัด (PNG สีใหญ่เกิน)
    d = _post(KKU_BASE + "/chat/completions", {
        "model": KKU_MODEL, "temperature": 0,
        "messages": [{"role": "user", "content": [{"type": "text", "text": KKU_PROMPT},
                                                  {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + jpg}}]}],
    }, {"Authorization": "Bearer " + _kku_key()}, timeout=300)
    if "choices" not in d:   # KKU ตอบ HTTP 200 พร้อม error ในเนื้อหา (เช่น เครดิตหมด)
        raise RuntimeError(str(d.get("error", d))[:300])
    return d["choices"][0]["message"]["content"] or ""


ENGINES = {"typhoon": ocr_typhoon, "tesseract": ocr_tesseract, "kku": ocr_kku}


def pages_to_ocr(path):
    from pypdf import PdfReader
    return [i for i, pg in enumerate(PdfReader(str(path)).pages) if needs_ocr(pg.extract_text() or "")]


def main():
    ap = argparse.ArgumentParser(description="OCR หน้า PDF ที่อ่านไม่ได้ในคลังความรู้ของ ลุงพี AI")
    ap.add_argument("--engine", choices=ENGINES, default="typhoon")
    ap.add_argument("--force", action="store_true", help="ทำใหม่แม้มีผล OCR ที่ตรงกับไฟล์แล้ว")
    ap.add_argument("--check", action="store_true", help="แค่แสดงจำนวนหน้าที่ต้อง OCR")
    ap.add_argument("--clean", action="store_true", help="ตัดคำบรรยายรูปออกจากผล OCR ที่มีอยู่ (ไม่ OCR ใหม่)")
    ap.add_argument("--no-reindex", action="store_true")
    ap.add_argument("only", nargs="*", help="ทำเฉพาะไฟล์ที่ชื่อมีคำเหล่านี้")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import pymupdf

    pdfs = sorted(p for p in KNOWLEDGE.rglob("*.pdf") if not any(part.startswith(".") for part in p.relative_to(KNOWLEDGE).parts))
    if a.only:
        pdfs = [p for p in pdfs if any(w.lower() in p.name.lower() for w in a.only)]
    if a.clean:
        changed = clean_existing(pdfs)
        print(f"เสร็จ: ตัดคำบรรยายรูปใน {changed} ไฟล์", flush=True)
        if changed and not a.no_reindex:
            reindex()
        return
    engine = ENGINES[a.engine]
    changed, failed_total, check_files, check_pages = 0, 0, 0, 0
    # ไฟล์ที่ตรวจแล้วว่าไม่มีหน้าต้อง OCR: จำลายเซ็นไว้ ไม่ต้องอ่าน PDF ทุกไฟล์ใหม่ทุกครั้ง (ไฟล์ใหญ่อ่านนานหลายนาที)
    scan_file = KNOWLEDGE / ".ocr" / "_no_ocr_needed.json"
    try:
        no_ocr = json.loads(scan_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        no_ocr = {}
    for p in pdfs:
        side = sidecar(p)
        rel = str(p.relative_to(KNOWLEDGE))
        old = json.loads(side.read_text(encoding="utf-8")) if side.is_file() else {}
        if old.get("sig") == file_sig(p) and not a.force and not old.get("failed"):
            continue
        if not a.force and no_ocr.get(rel) == file_sig(p):
            continue
        todo = pages_to_ocr(p)
        if not todo:
            no_ocr[rel] = file_sig(p)
            continue
        no_ocr.pop(rel, None)
        print(f"{p.relative_to(KNOWLEDGE)}: {len(todo)} หน้าต้อง OCR", flush=True)
        if a.check:
            check_pages += len(todo); check_files += 1
            continue
        doc = pymupdf.open(p)
        pages = {} if a.force else {int(k): v for k, v in (old.get("pages") or {}).items()} if old.get("sig") == file_sig(p) else {}
        raw = {int(k): v for k, v in (old.get("raw") or {}).items()} if pages else {}
        failed = []
        for i in todo:
            if i in pages:
                continue
            t0 = time.time()
            try:
                raw[i] = engine(doc[i])   # เก็บข้อความดิบ: เปลี่ยนวิธีทำความสะอาดภายหลังได้โดยไม่ต้อง OCR ใหม่
                pages[i] = tidy(raw[i])
                print(f"   หน้า {i + 1}: {len(pages[i])} ตัวอักษร · {time.time() - t0:.0f} วินาที", flush=True)
            except Exception as e:
                failed.append(i)
                print(f"   หน้า {i + 1}: ไม่สำเร็จ — {e}", flush=True)
            # บันทึกทุกหน้า: หยุดกลางทางแล้วรันใหม่จะทำต่อจากหน้าที่ค้าง
            side.parent.mkdir(parents=True, exist_ok=True)
            side.write_text(json.dumps({"sig": file_sig(p), "engine": a.engine, "failed": failed,
                                        "pages": {str(k): v for k, v in sorted(pages.items())},
                                        "raw": {str(k): v for k, v in sorted(raw.items())}},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
        changed += 1
        failed_total += len(failed)
    existing = {str(p.relative_to(KNOWLEDGE)) for p in pdfs} if not a.only else None
    if existing is not None:   # ลืมไฟล์ที่ถูกลบไปแล้ว
        no_ocr = {k: v for k, v in no_ocr.items() if k in existing}
    scan_file.parent.mkdir(parents=True, exist_ok=True)
    scan_file.write_text(json.dumps(no_ocr, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.check:
        print(f"ตรวจเสร็จ: {check_files} ไฟล์ {check_pages} หน้าที่ต้อง OCR" if check_pages else
              "ตรวจเสร็จ: ไม่มีหน้าที่ต้อง OCR (ทุกไฟล์อ่านได้ หรือทำ OCR แล้ว)", flush=True)
        return
    print(f"เสร็จ: OCR {changed} ไฟล์ · หน้าที่ไม่สำเร็จ {failed_total}", flush=True)
    if changed and not a.no_reindex:
        reindex()


def reindex():
    try:
        r = _post(GATEWAY + "/api/rag/reindex", {"force": False}, timeout=30)
        print("สั่ง gateway จัดคลังเฉพาะไฟล์ที่เปลี่ยน:", r.get("msg"), flush=True)
    except Exception as e:
        print("สั่ง gateway จัดคลังไม่ได้ (gateway ไม่ได้เปิด?) — เปิด ลุงพี AI แล้วจะจัดเองตอนเริ่ม:", e, flush=True)


def clean_existing(pdfs):
    """ใช้ tidy ใหม่กับผล OCR ที่มีอยู่: มีข้อความดิบ -> ทำความสะอาดใหม่จากดิบ / ไม่มี (OCR รุ่นแรก) -> ตัดย่อหน้าคำบรรยายรูป"""
    changed = 0
    for p in pdfs:
        side = sidecar(p)
        if not side.is_file():
            continue
        d = json.loads(side.read_text(encoding="utf-8"))
        raw = d.get("raw") or {}
        new = {k: (tidy(raw[k]) if k in raw else strip_figure_paragraphs(v)) for k, v in d["pages"].items()}
        if new != d["pages"]:
            removed = sum(len(d["pages"][k]) - len(new[k]) for k in new)
            d["pages"] = new
            side.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{p.relative_to(KNOWLEDGE)}: ตัดออก {removed} ตัวอักษร", flush=True)
            changed += 1
    return changed


if __name__ == "__main__":
    main()
