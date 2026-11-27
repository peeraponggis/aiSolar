# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""After a render: post text, a thumbnail, and a copy of everything in F:\\LocalAI\\clips."""
import json
import os
import re
import shutil
import subprocess
from datetime import datetime

from PIL import Image, ImageDraw

from scripts.create_video import FFMPEG, FONTS_DIR, _wrap_line
from scripts.thai_text import draw_text, measure_text

CLIPS_DIR = os.getenv("CLIPS_DIR", "F:/LocalAI/clips")
TITLE_FONT = os.path.join(FONTS_DIR, "Kanit-Regular.ttf")


def write_post(output_dir: str, post: dict) -> str:
    """post.json (for the app) and post.txt (ready to paste)."""
    with open(os.path.join(output_dir, "post.json"), "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)
    parts = [post.get("title", ""), post.get("description", ""), " ".join(post.get("hashtags", []))]
    txt = os.path.join(output_dir, "post.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write("\n\n".join(p for p in parts if p).strip() + "\n")
    return txt


def make_thumbnail(source: str, title: str, out_path: str, size: tuple[int, int]) -> str | None:
    """The first scene's own picture (no subtitles or overlays) filled to the
    video size, with the title in large type over a dark band."""
    frame = out_path + ".frame.png"
    w, h = size
    is_video = os.path.splitext(source)[1].lower() in (".mp4", ".mov", ".webm", ".mkv")
    seek = ["-ss", "1.0"] if is_video else []
    subprocess.run([FFMPEG, "-y", "-v", "error", *seek, "-i", source, "-frames:v", "1",
                    "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h}",
                    frame], capture_output=True, timeout=60)
    if not os.path.exists(frame):
        return None
    img = Image.open(frame).convert("RGB")
    os.remove(frame)
    w, h = img.size
    size = int(min(w, h) / 9.5)
    lines = _wrap_line(title, max(8, int(w / (size * 0.55))))[:3]
    line_h = int(size * 1.35)
    block = line_h * len(lines) + size
    top = int(h * 0.62) - block // 2 if h > w else h - block - int(h * 0.08)

    shade = Image.new("L", (w, h), 0)
    ImageDraw.Draw(shade).rectangle([0, top - size // 2, w, top + block], fill=150)
    img = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), img, shade)
    y = top
    for line in lines:
        x = (w - measure_text(line, TITLE_FONT, size)) / 2
        draw_text(img, (x, y), line, TITLE_FONT, size, fill=(255, 214, 0),
                  stroke_width=max(3, size // 14), stroke_fill=(0, 0, 0))
        y += line_h
    img.save(out_path, quality=92)
    return out_path


def _folder_name(title: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|\r\n]+', " ", title).strip()[:60].strip() or "clip"
    return f"{datetime.now():%Y-%m-%d_%H%M}_{safe}"


def save_to_clips(video_paths: dict, extra_files: list[str], title: str) -> str:
    """Copy the finished clip (all ratios) plus post text and thumbnail into
    F:\\LocalAI\\clips\\<date_time>_<title>\\ — automatic, never prompts."""
    base = os.path.normpath(os.path.join(CLIPS_DIR, _folder_name(title)))
    folder, n = base, 2
    while os.path.exists(folder):
        folder, n = f"{base}_{n}", n + 1
    os.makedirs(folder)
    for ratio, path in video_paths.items():
        if os.path.exists(path):
            shutil.copy2(path, os.path.join(folder, f"{ratio.replace(':', 'x')}.mp4"))
    for path in extra_files:
        if path and os.path.exists(path):
            shutil.copy2(path, os.path.join(folder, os.path.basename(path)))
    return folder
