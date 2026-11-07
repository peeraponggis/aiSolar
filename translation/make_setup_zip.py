# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

# -*- coding: utf-8 -*-
"""สร้างชุดติดตั้ง LocalTranslator-setup.zip จาก dist\\LocalTranslator (หลัง build exe แล้ว)
    py make_setup_zip.py
ไม่รวมไฟล์ใช้งานส่วนตัว (settings.json, history.json, *.log) และไฟล์สำรอง (*.bak*)
ปลายทางแตก zip แล้วรัน Install-LocalTranslator.bat — ติดตั้ง Ollama + โมเดลให้เองทั้งหมด
"""
import fnmatch
import os
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app_version import VERSION  # noqa: E402

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "dist" / "LocalTranslator"
OUT = ROOT / "LocalTranslator-setup.zip"
SKIP = ["settings.json", "settings.json.bak*", "history.json", "*.log", "*.bak-*", "*.bak", "__pycache__"]


def skip(name):
    return any(fnmatch.fnmatch(name, p) for p in SKIP)


def main():
    if not (SRC / "LocalTranslator.exe").exists():
        sys.exit(f"ไม่พบ {SRC / 'LocalTranslator.exe'} — build ก่อน: py -m PyInstaller LocalTranslator.spec --noconfirm")
    n = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dp, dns, fns in os.walk(SRC):
            dns[:] = [d for d in dns if not skip(d)]
            for fn in fns:
                if skip(fn):
                    continue
                p = Path(dp) / fn
                z.write(p, "LocalTranslator/" + p.relative_to(SRC).as_posix())
                n += 1
    print(f"สร้าง {OUT} (v{VERSION}) {n} ไฟล์ {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
