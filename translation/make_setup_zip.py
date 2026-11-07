# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

# -*- coding: utf-8 -*-
"""สร้างชุดติดตั้ง 2 แบบ (รันหลัง build_exe.bat)
    LocalTranslator-setup.zip  ชุดแจกจ่าย (~31 MB) จาก dist_lite\\LocalTranslator — ไม่มีพูดถามด้วยเสียง
    LocalTranslator-full.zip   ชุดเต็ม (~181 MB) จาก dist\\LocalTranslator — มีพูดถามด้วยเสียง (เครื่องตัวเอง)
ไม่รวมไฟล์ใช้งานส่วนตัว (settings.json, history.json, *.log) และไฟล์สำรอง (*.bak*)
ปลายทางแตก zip แล้วรัน Install-LocalTranslator.bat — ติดตั้ง Ollama + โมเดลให้เองทั้งหมด
    py make_setup_zip.py [lite|full|all]
"""
import fnmatch
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app_version import VERSION  # noqa: E402

ROOT = Path(__file__).resolve().parent
EDITIONS = {
    "lite": (ROOT / "dist_lite" / "LocalTranslator", ROOT / "LocalTranslator-setup.zip"),
    "full": (ROOT / "dist" / "LocalTranslator", ROOT / "LocalTranslator-full.zip"),
}
EXTRAS = ["Install-LocalTranslator.bat", "README-install.txt", "README-translator.md", "glossary.txt", "translator.ico", "translator.png"]
SKIP = ["settings.json", "settings.json.bak*", "history.json", "*.log", "*.bak-*", "*.bak", "__pycache__", "_stt_selftest.wav"]


def skip(name):
    return any(fnmatch.fnmatch(name, p) for p in SKIP)


def build(edition):
    src, out = EDITIONS[edition]
    if not (src / "LocalTranslator.exe").exists():
        sys.exit(f"ไม่พบ {src / 'LocalTranslator.exe'} — build ก่อน: build_exe.bat {edition}")
    missing = [f for f in EXTRAS if not (src / f).exists()]
    if missing:
        sys.exit(f"{src} ขาดไฟล์ {missing} (build_exe.bat คัดลอกให้จาก dist\\LocalTranslator)")
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dp, dns, fns in os.walk(src):
            dns[:] = [d for d in dns if not skip(d)]
            for fn in fns:
                if skip(fn):
                    continue
                p = Path(dp) / fn
                z.write(p, "LocalTranslator/" + p.relative_to(src).as_posix())
                n += 1
    print(f"{edition:4} v{VERSION}: {out.name} {n} ไฟล์ {out.stat().st_size / 1e6:.1f} MB")


def main():
    what = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    for ed in (EDITIONS if what == "all" else [what]):
        build(ed)


if __name__ == "__main__":
    main()
