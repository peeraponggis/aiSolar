# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""AI images for scenes, drawn by AI-Bridge-Launcher (FLUX.2 klein locally, or Gemini)."""
import asyncio
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

SCRIPTS = Path(os.environ.get("AIBRIDGE_SCRIPTS", r"F:\enterprise\aipass-auto-router\scripts"))
# Must be a Python with torch + diffusers (the machine's main Python has them).
IMAGE_PYTHON = os.environ.get("AI_IMAGE_PYTHON", sys.executable)
WORKER = Path(__file__).with_name("ai_image_worker.py")
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "ai_image_worker.log"
ENGINE_LABELS = {"flux": "FLUX.2 klein (คุณภาพ)", "flux-fast": "FLUX.2 klein (เร็ว)",
                 "sd-turbo": "SD-Turbo", "gemini": "Gemini (คลาวด์ คิดเงินต่อภาพ)"}


def is_available() -> bool:
    return (SCRIPTS / "local_image.py").exists()


def _run_batch(prompts: list[str], engine: str, shape: str,
               progress: Callable | None) -> list[str | None]:
    jobs = [{"prompt": p, "shape": shape} for p in prompts]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "AIBRIDGE_SCRIPTS": str(SCRIPTS)}
    # Model loading prints a lot of progress bars to stderr; an unread pipe
    # would fill up and block the worker, so it goes to a log file instead.
    LOG_PATH.parent.mkdir(exist_ok=True)
    log_file = open(LOG_PATH, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        [IMAGE_PYTHON, str(WORKER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=log_file, encoding="utf-8", errors="replace", env=env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    # A model load plus ~40 s per image; kill a hung worker instead of waiting forever.
    watchdog = threading.Timer(180 + 120 * len(prompts), proc.kill)
    watchdog.start()
    results: list[str | None] = [None] * len(prompts)
    try:
        proc.stdin.write(json.dumps({"jobs": jobs, "engine": engine}))
        proc.stdin.close()
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get("type") == "done":
                results[msg["index"]] = msg["path"]
                if progress:
                    progress(msg["index"], None)
            elif msg.get("type") == "fail":
                print(f"AI image {msg['index'] + 1} failed: {msg.get('message')}")
            elif msg.get("type") == "progress" and progress:
                progress(msg["index"], msg.get("stage"))
        proc.wait(timeout=30)
    finally:
        watchdog.cancel()
        log_file.close()
    if proc.returncode not in (0, None) and not any(results):
        tail = LOG_PATH.read_text(encoding="utf-8", errors="replace")[-400:]
        raise RuntimeError(f"AI image worker failed: {tail}")
    return results


async def generate_images(prompts: list[str], engine: str = "flux", shape: str = "portrait",
                          progress: Callable | None = None) -> list[str | None]:
    """One path (or None on failure) per prompt, in order."""
    if not prompts:
        return []
    if not is_available():
        raise RuntimeError(f"ไม่พบ AI-Bridge-Launcher ที่ {SCRIPTS}")
    return await asyncio.to_thread(_run_batch, prompts, engine, shape, progress)
