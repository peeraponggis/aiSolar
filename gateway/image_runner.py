# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

# -*- coding: utf-8 -*-
"""image_runner.py — สร้างภาพด้วยสคริปต์ของ AI-Bridge-Launcher (local_image / gemini_image) ตัวเดียวกัน
ภาพจึงไปอยู่ที่เดียวกัน (F:\\LocalAI\\clip_bank\\img + prompts\\) และได้พฤติกรรมเดียวกันทุกอย่าง

ใช้ร่วมกันโดย ลุงพี AI gateway และ ลุงพี Agent — รันด้วย python ของเครื่อง (มี torch/CUDA) แยกเป็นโปรเซส
เพื่อไม่ต้องยัด torch เข้า gateway.exe และคืน VRAM ทันทีที่สร้างเสร็จ

    python image_runner.py '{"prompt": "แมวส้ม", "engine": "flux", "shape": "auto", "count": 1}'

พิมพ์ JSON ทีละบรรทัดทาง stdout: {"type":"progress","stage":...,"frac":0.3} ... แล้วจบด้วย
{"type":"result", ...ผลจากสคริปต์} หรือ {"type":"error","message":...}
"""
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(os.environ.get("AIBRIDGE_SCRIPTS", r"F:\enterprise\aipass-auto-router\scripts"))
OUT_DIR = Path(os.environ.get("LOCAL_IMAGE_DIR") or r"F:\LocalAI\clip_bank\img")
# engine -> (ระบบ, โมเดล, โหมด) ตรงกับตัวเลือกใน AI-Bridge-Launcher
ENGINES = {
    "flux": ("local", "flux2-klein", "quality"),
    "flux-fast": ("local", "flux2-klein", "fast"),
    "sd-turbo": ("local", "sd-turbo", "fast"),
    "sd-turbo-quality": ("local", "sd-turbo", "quality"),
    "gemini": ("gemini", "gemini-3.1-flash-image", None),
    "gemini-pro": ("gemini", "gemini-3-pro-image", None),
}
GEMINI_ASPECT = {"square": "1:1", "portrait": "9:16", "landscape": "16:9"}


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def run(req):
    prompt = (req.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("ไม่มีคำอธิบายภาพ")
    kind, model, mode = ENGINES.get(req.get("engine") or "flux", ENGINES["flux"])
    shape = req.get("shape") or "auto"
    count = max(1, min(int(req.get("count") or 1), 4))
    sys.path.insert(0, str(SCRIPTS))
    import local_image   # import เบา: torch โหลดตอนเรียก generate เท่านั้น
    if shape == "auto":
        shape = local_image.detect_shape(prompt) or "square"
    if kind == "gemini":   # วาดบนคลาวด์ ไม่ใช้ GPU ในเครื่อง จึงไม่ต้องเข้าคิว
        import gemini_image
        emit({"type": "progress", "stage": f"รอ {model} สร้างภาพ", "frac": 0.2})
        res = gemini_image.generate(prompt, model, GEMINI_ASPECT[shape])
        res.update(count=len(res["paths"]), shape=shape, engine="gemini")
        return res
    # คิว GPU ข้ามโปรแกรม (Launcher/ลุงพี AI/Agent) และการปล่อย VRAM ของ Ollama อยู่ใน local_image.generate แล้ว
    res = local_image.generate(prompt, mode, shape, count, model=model,
                               progress=lambda stage, frac: emit({"type": "progress", "stage": stage, "frac": frac}))
    res.update(engine="local")
    return res


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        req = json.loads(sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read())
        res = run(req)
        res["names"] = [Path(p).name for p in res.get("paths", [])]
        res["out_dir"] = str(OUT_DIR)
        emit({"type": "result", **res})
    except Exception as e:
        emit({"type": "error", "message": str(e)[:600]})
        sys.exit(1)


if __name__ == "__main__":
    main()
