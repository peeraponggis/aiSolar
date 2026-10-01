#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/shell.py - รันคำสั่ง PowerShell (Tier C - เสี่ยงสูงสุด ต้องขอ confirm จากผู้ใช้ก่อนเสมอ
ดู safety.py)
"""
import logging
import subprocess

log = logging.getLogger(__name__)


def run_shell(command, timeout=30):
    if not (command or "").strip():
        return {"ok": False, "error": "ไม่ได้ระบุคำสั่ง"}
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"ok": result.returncode == 0, "stdout": result.stdout[-4000:],
                "stderr": result.stderr[-2000:], "returncode": result.returncode}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"คำสั่งใช้เวลานานเกิน {timeout} วินาที"}
    except Exception as e:
        log.exception("run_shell ผิดพลาด (command=%s)", command)
        return {"ok": False, "error": str(e)}
