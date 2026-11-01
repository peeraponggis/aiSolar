# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""Animated stat cards (HyperFrames: HTML + GSAP rendered by headless Chrome).

A card is just another scene clip: rendered to MP4 at the scene's length and
handed to the normal FFmpeg pipeline. Every number on a card must already be
in the scene's own words — the LLM only points at it, never invents it.
"""
import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOCALAI_DIR = BASE_DIR.parent
TEMPLATE_DIR = BASE_DIR / "templates" / "hyperframes" / "stat_card"
HF_PACKAGE = "hyperframes@0.8.225"
LOG_PATH = BASE_DIR / "logs" / "graphic_cards.log"

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")
_lock = asyncio.Lock()


def _node() -> list[str] | None:
    """[node, npx-cli.js] — calling node directly avoids running npx.cmd through cmd.exe."""
    node = shutil.which("node")
    if not node:
        return None
    cli = Path(node).parent / "node_modules" / "npm" / "bin" / "npx-cli.js"
    if cli.exists():
        return [node, str(cli)]
    npx = shutil.which("npx")
    return [npx] if npx else None


def is_available() -> bool:
    cmd = _node()
    if not cmd or not (TEMPLATE_DIR / "index.html").exists():
        return False
    try:
        out = subprocess.run([shutil.which("node"), "--version"], capture_output=True, check=False,
                             text=True, timeout=10).stdout
        return int(out.strip().lstrip("v").split(".")[0]) >= 22
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def _env() -> dict:
    """Keep every HyperFrames file on this drive (no writes to C:) and telemetry off."""
    from scripts.utils import FFMPEG
    tmp = LOCALAI_DIR / "tmp"
    tmp.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update({
        "USERPROFILE": str(LOCALAI_DIR / "tools" / "hyperframes-home"),
        "npm_config_cache": str(LOCALAI_DIR / ".npm-cache"),
        "PUPPETEER_CACHE_DIR": str(LOCALAI_DIR / "tools" / "puppeteer-cache"),
        "HYPERFRAMES_EXTRACT_CACHE_DIR": str(tmp / "hf-cache"),
        "TEMP": str(tmp), "TMP": str(tmp),
        "DO_NOT_TRACK": "1", "HYPERFRAMES_NO_TELEMETRY": "1", "HYPERFRAMES_SKIP_SKILLS": "1",
        "PATH": os.path.dirname(FFMPEG) + os.pathsep + env.get("PATH", ""),
    })
    return env


# ── Stat checking ──

def _numbers(text: str) -> list[str]:
    return [m.group(0).replace(",", "") for m in _NUM.finditer(str(text).translate(_THAI_DIGITS))]


def clean_stat(stat, source_text: str) -> dict | None:
    """Validated card fields, or None. The value (and any number in the other
    fields) must appear in the scene's original text."""
    if not isinstance(stat, dict):
        return None
    try:
        value = float(str(stat.get("value", "")).replace(",", ""))
    except ValueError:
        return None
    spoken = _numbers(source_text)
    token = next((t for t in spoken if float(t) == value), None)
    if token is None:
        return None
    fields = {k: str(stat.get(k) or "").strip()[:limit]
              for k, limit in (("label", 40), ("unit", 24), ("badge", 14), ("caption", 70))}
    allowed = {float(t) for t in spoken}
    if any(float(n) not in allowed for f in fields.values() for n in _numbers(f)):
        return None
    decimals = len(token.split(".")[1]) if "." in token else 0
    return {"value": value, "decimals": min(decimals, 2), **fields}


# ── Rendering ──

async def render_stat_card(stat: dict, out_path: str, duration: float,
                           orientation: str = "portrait", accent: str = "#f5c542") -> bool:
    """Render one card to out_path (MP4, at least `duration` seconds). False on failure."""
    cmd = _node()
    if not cmd:
        return False
    w, h, scale = (1920, 1080, 0.75) if orientation == "landscape" else (1080, 1920, 1)
    seconds = max(3.0, round(duration + 1.0, 2))  # clips loop in the pipeline: never run short
    out_path = str(Path(out_path).resolve())  # the CLI resolves -o against its own cwd
    work = Path(out_path).with_suffix("")
    work = work.parent / f"_card_{work.name}"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(TEMPLATE_DIR, work)
    html = (work / "index.html").read_text(encoding="utf-8")
    for key, val in (("__W__", w), ("__H__", h), ("__S__", scale), ("__DURATION__", seconds)):
        html = html.replace(key, str(val))
    (work / "index.html").write_text(html, encoding="utf-8")
    variables = {"kicker": stat.get("label", ""), "value": stat["value"],
                 "decimals": stat.get("decimals", 0), "unit": stat.get("unit", ""),
                 "badge": stat.get("badge", ""), "caption": stat.get("caption", ""),
                 "accent": accent}
    (work / "variables.json").write_text(json.dumps(variables, ensure_ascii=False), encoding="utf-8")
    rendered = work / "renders" / "card.mp4"

    def run() -> bool:
        LOG_PATH.parent.mkdir(exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", errors="replace") as log:
            log.write(f"\n== {out_path} ({seconds}s)\n")
            log.flush()
            try:
                subprocess.run(cmd + ["--yes", HF_PACKAGE, "render", "-o", str(rendered),
                                      "--variables-file", "variables.json", "--quiet"],
                               cwd=str(work), env=_env(), stdout=log, stderr=log,
                               timeout=180 + 8 * seconds, check=False)
            except subprocess.TimeoutExpired:
                log.write("timeout\n")
                return False
        if not rendered.exists() or rendered.stat().st_size < 1000:
            return False
        shutil.move(str(rendered), out_path)
        return True

    try:
        async with _lock:  # one Chrome render farm at a time
            return await asyncio.to_thread(run)
    finally:
        shutil.rmtree(work, ignore_errors=True)
