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
tools/image.py - วาดภาพจากคำสั่ง (เช่น "วาดรูปแมวส้ม") ด้วย image_runner.py ตัวเดียวกับ ลุงพี AI gateway
ซึ่งเรียกสคริปต์ของ AI-Bridge-Launcher — ภาพจึงเก็บที่ F:\\LocalAI\\clip_bank\\img เหมือนกันทุกโปรแกรม
และใช้ล็อก GPU ร่วมกัน (วาดได้ทีละงาน) วาดเสร็จแล้วเปิดภาพให้ผู้ใช้ดูทันที
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)
RUNNER = Path(os.environ.get("LUNGPEE_IMAGE_RUNNER", r"F:\LocalAI\gateway\image_runner.py"))
TIMEOUT_S = 600


def _python():
    # agent รันด้วย pythonw.exe — ใช้ python.exe ข้างกัน (ตัวเดียวกันที่มี torch/CUDA) เพื่ออ่าน stdout ได้
    exe = Path(sys.executable)
    cand = exe.with_name("python.exe")
    return str(cand if cand.is_file() else exe)


def generate_image(prompt, shape="auto", engine="flux"):
    if not (prompt or "").strip():
        return {"ok": False, "error": "ไม่มีคำอธิบายภาพ"}
    if not RUNNER.is_file():
        return {"ok": False, "error": f"ไม่พบตัวสร้างภาพ {RUNNER}"}
    req = {"prompt": prompt, "engine": engine, "shape": shape or "auto", "count": 1}
    try:
        proc = subprocess.run([_python(), str(RUNNER), json.dumps(req, ensure_ascii=False)],
                              capture_output=True, timeout=TIMEOUT_S, cwd=str(RUNNER.parent),
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"สร้างภาพนานเกิน {TIMEOUT_S // 60} นาที"}
    last = None
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("type") in ("result", "error"):
            last = d
    if not last or last["type"] == "error":
        msg = (last or {}).get("message") or f"ตัวสร้างภาพหยุดทำงาน (exit {proc.returncode})"
        log.warning("สร้างภาพไม่สำเร็จ: %s", msg)
        return {"ok": False, "error": msg}
    path = last["paths"][0]
    try:
        os.startfile(path)   # เปิดภาพให้ดูทันที (โปรแกรมดูภาพของ Windows)
    except OSError:
        log.warning("เปิดภาพ %s ไม่ได้", path, exc_info=True)
    return {"ok": True, "path": path, "model": last.get("model"), "size": last.get("size") or last.get("aspect"),
            "seconds": last.get("seconds"), "message": "วาดเสร็จแล้ว เปิดภาพให้ดูแล้ว"}
