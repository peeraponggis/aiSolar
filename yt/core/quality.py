# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

"""Checks that decide whether an automatic clip may render without a human look."""
import os

from scripts.script_tools import leftover_english
from scripts.utils import get_audio_duration


def check_before_render(audio_path: str, preset: dict, scenes: list[dict],
                        media: list[dict] | None, audio_report: dict,
                        script_problems: list[str], clone_requested: bool) -> list[str]:
    """Reasons a person should look first; an empty list means it is safe to render."""
    reasons = list(script_problems)
    if audio_report.get("used_gtts"):
        reasons.append("edge-tts ใช้ไม่ได้ ใช้ gTTS แทน (เสียงไม่ตรงที่เลือก)")
    if clone_requested and audio_report.get("clone_failed"):
        reasons.append("โคลนเสียงไม่สำเร็จ ใช้เสียง TTS ปกติแทน")

    seconds = get_audio_duration(audio_path) if audio_path and os.path.exists(audio_path) else 0
    low, high = preset["min_s"], preset["max_s"]
    if not low <= seconds <= high:
        reasons.append(f"เสียงยาว {seconds:.0f} วินาที นอกช่วงที่ตั้งไว้ ({low}-{high} วินาที)")

    english = sorted({w for s in scenes for w in leftover_english(s["text"])})
    if english:
        reasons.append("ยังมีคำอังกฤษที่ไม่มีคำอ่าน: " + ", ".join(english[:6]))

    if media is not None:
        missing = [r["index"] + 1 for r in media if not r.get("file")]
        fallback = [r["index"] + 1 for r in media if r.get("fallback")]
        if missing:
            reasons.append(f"ฉาก {', '.join(map(str, missing))} ไม่มีสื่อ")
        if fallback:
            reasons.append(f"ฉาก {', '.join(map(str, fallback))} ใช้สื่อจากหัวข้อรวม (หาตรงฉากไม่ได้)")
    return reasons


def check_after_render(video_paths: dict, audio_seconds: float) -> list[str]:
    from scripts.create_video import _get_video_stream_duration
    problems = []
    for ratio, path in video_paths.items():
        dur = _get_video_stream_duration(path) if os.path.exists(path) else 0
        if abs(dur - audio_seconds) > 1.5:
            problems.append(f"วิดีโอ {ratio} ยาว {dur:.1f} วิ ไม่ตรงกับเสียง {audio_seconds:.1f} วิ")
    return problems
