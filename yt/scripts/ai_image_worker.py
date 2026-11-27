# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""Draw several images in one process with AI-Bridge-Launcher's own code, so
the model loads once for the whole batch (FLUX.2 klein takes ~54 s to load).

Run as a child process (it imports torch):
    python ai_image_worker.py < {"jobs": [{"prompt": "...", "shape": "portrait"}], "engine": "flux"}

Prints one JSON object per line: {"type": "progress", "index", "stage", "frac"},
{"type": "done", "index", "path"} or {"type": "fail", "index", "message"}, then {"type": "end"}.
"""
import json
import os
import sys
from pathlib import Path

SCRIPTS = Path(os.environ.get("AIBRIDGE_SCRIPTS", r"F:\enterprise\aipass-auto-router\scripts"))
# engine -> (kind, model, mode); same choices as AI-Bridge-Launcher / gateway image_runner
ENGINES = {
    "flux": ("local", "flux2-klein", "quality"),
    "flux-fast": ("local", "flux2-klein", "fast"),
    "sd-turbo": ("local", "sd-turbo", "quality"),
    "gemini": ("gemini", "gemini-3.1-flash-image", None),
}
GEMINI_ASPECT = {"square": "1:1", "portrait": "9:16", "landscape": "16:9"}


def emit(obj: dict):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    req = json.loads(sys.stdin.read())
    kind, model, mode = ENGINES.get(req.get("engine") or "flux", ENGINES["flux"])
    sys.path.insert(0, str(SCRIPTS))
    import local_image
    for i, job in enumerate(req.get("jobs", [])):
        shape = job.get("shape") or "portrait"
        try:
            if kind == "gemini":
                import gemini_image
                res = gemini_image.generate(job["prompt"], model, GEMINI_ASPECT[shape])
            else:
                res = local_image.generate(
                    job["prompt"], mode, shape, 1, model=model,
                    progress=lambda stage, frac, i=i: emit({"type": "progress", "index": i,
                                                            "stage": stage, "frac": frac}))
            path = res.get("path") or (res.get("paths") or [None])[0]
            if not path:
                raise RuntimeError("no image returned")
            emit({"type": "done", "index": i, "path": str(path)})
        except Exception as e:
            emit({"type": "fail", "index": i, "message": str(e)[:300]})
    emit({"type": "end"})


if __name__ == "__main__":
    main()
