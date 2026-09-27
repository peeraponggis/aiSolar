import os
import re
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from scripts.utils import get_audio_duration

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")
FONT_PATH = os.getenv("FONT_PATH", "F:/LocalAI/tools/fonts/Sarabun-Regular.ttf")
FONTS_DIR = os.path.dirname(FONT_PATH)

FONT_MAP = {
    "sarabun": os.path.join(FONTS_DIR, "Sarabun-Regular.ttf"),
    "kanit": os.path.join(FONTS_DIR, "Kanit-Regular.ttf"),
    "prompt": os.path.join(FONTS_DIR, "Prompt-Regular.ttf"),
    "mitr": os.path.join(FONTS_DIR, "Mitr-Regular.ttf"),
}

XFADE_DUR = 0.5


def _extract_media_order(path: str) -> int:
    m = re.match(r"(\d+)_", os.path.basename(path))
    return int(m.group(1)) if m else 999


ASPECT_CONFIGS = {
    "9:16": {
        "w": 1080, "h": 1920, "fps": 30,
        "audio_br": "128k",
        "pre_w": 1920, "pre_h": 3412,
        "sub_fs": 42, "sub_y": "h-250",
        "sub_max_chars": 35,
        "overlay_fs": 36,
    },
    "16:9": {
        "w": 1920, "h": 1080, "fps": 30,
        "audio_br": "192k",
        "pre_w": 3412, "pre_h": 1920,
        "sub_fs": 38, "sub_y": "h-250",
        "sub_max_chars": 65,
        "overlay_fs": 32,
    },
}

_nvenc_ok = None


def _check_nvenc() -> bool:
    global _nvenc_ok
    if _nvenc_ok is not None:
        return _nvenc_ok
    try:
        r = subprocess.run(
            [FFMPEG, "-y", "-f", "lavfi", "-i", "color=s=64x64:d=0.1",
             "-c:v", "h264_nvenc", "-frames:v", "1", "-f", "null", "-"],
            capture_output=True, timeout=10,
        )
        _nvenc_ok = r.returncode == 0
    except Exception:
        _nvenc_ok = False
    if not _nvenc_ok:
        print("NVENC not available, using libx264")
    return _nvenc_ok


def _video_enc_args() -> list[str]:
    if _check_nvenc():
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23",
                "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p"]


def _parse_script_sections(script: str) -> list[str]:
    lines = []
    for line in script.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"\[.*?\]", "", line).strip()
        cleaned = re.sub(r"^[—\-–]+\s*", "", cleaned).strip()
        if cleaned and len(cleaned) > 5:
            lines.append(cleaned)
    return lines


def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\u2019")
    text = text.replace(":", "\\:")
    text = text.replace("%", "%%")
    return text


def _wrap_text(text: str, max_chars: int, max_lines: int = 2) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    lines: list[str] = []
    remaining = text
    for i in range(max_lines):
        if not remaining:
            break
        if i == max_lines - 1 or len(remaining) <= max_chars:
            if len(remaining) > max_chars:
                remaining = remaining[:max_chars]
            lines.append(remaining)
            remaining = ""
            break
        break_at = max_chars
        space_pos = remaining.rfind(" ", max(0, max_chars // 2), max_chars + 1)
        if space_pos > 0:
            break_at = space_pos
        lines.append(remaining[:break_at].rstrip())
        remaining = remaining[break_at:].lstrip()
    return lines


def _build_subtitle_filter(sections: list[str], total_duration: float,
                           fontsize: int = 42, y_expr: str = "h-200",
                           max_chars: int = 35) -> str:
    if not sections:
        return ""
    segment_dur = total_duration / len(sections)
    font_path = FONT_PATH.replace("\\", "/").replace(":", "\\:")
    line_height = int(fontsize * 1.5)
    filters = []
    for i, text in enumerate(sections):
        lines = _wrap_text(text, max_chars)
        start = i * segment_dur
        end = start + segment_dur
        num_lines = len(lines)
        for j, line_text in enumerate(lines):
            escaped = _escape_drawtext(line_text)
            y_offset = (num_lines - 1 - j) * line_height
            y = y_expr if y_offset == 0 else f"{y_expr}-{y_offset}"
            f = (
                f"drawtext=fontfile='{font_path}'"
                f":text='{escaped}'"
                f":fontsize={fontsize}"
                f":fontcolor=white"
                f":borderw=3"
                f":bordercolor=black"
                f":x=(w-text_w)/2"
                f":y={y}"
                f":enable='between(t\\,{start:.2f}\\,{end:.2f})'"
            )
            filters.append(f)
    return ",".join(filters)


SPEAKER_COLORS = {"A": "white", "B": "#FFD700"}


def _build_dialogue_subtitle_filter(
    timing: list[dict], fontsize: int = 42, y_expr: str = "h-200",
    max_chars: int = 35,
) -> str:
    if not timing:
        return ""
    font_path = FONT_PATH.replace("\\", "/").replace(":", "\\:")
    line_height = int(fontsize * 1.5)
    filters = []
    for entry in timing:
        text = entry["text"]
        lines = _wrap_text(text, max_chars)
        speaker = entry.get("speaker", "A")
        color = SPEAKER_COLORS.get(speaker, "white")
        start = entry["start"]
        end = entry["end"]
        num_lines = len(lines)
        for j, line_text in enumerate(lines):
            escaped = _escape_drawtext(line_text)
            y_offset = (num_lines - 1 - j) * line_height
            y = y_expr if y_offset == 0 else f"{y_expr}-{y_offset}"
            f = (
                f"drawtext=fontfile='{font_path}'"
                f":text='{escaped}'"
                f":fontsize={fontsize}"
                f":fontcolor={color}"
                f":borderw=3"
                f":bordercolor=black"
                f":x=(w-text_w)/2"
                f":y={y}"
                f":enable='between(t\\,{start:.2f}\\,{end:.2f})'"
            )
            filters.append(f)
    return ",".join(filters)


def _resolve_font(font_name: str) -> str:
    path = FONT_MAP.get(font_name, FONT_PATH)
    if not os.path.exists(path):
        path = FONT_PATH
    return path.replace("\\", "/").replace(":", "\\:")


def _build_overlay_text_filter(text: str, fontsize: int,
                               font_name: str, animation: str,
                               duration: float) -> str:
    if not text.strip():
        return ""
    font_path = _resolve_font(font_name)
    escaped = _escape_drawtext(text.strip())
    y_pos = "h-350"

    base = (
        f"drawtext=fontfile='{font_path}'"
        f":text='{escaped}'"
        f":fontsize={fontsize}"
        f":fontcolor=white"
        f":borderw=2"
        f":bordercolor=black@0.8"
        f":x=(w-text_w)/2"
    )

    if animation == "fade":
        dur = duration
        base += (
            f":y={y_pos}"
            f":alpha='if(lt(t\\,0.5)\\,t/0.5\\,"
            f"if(gt(t\\,{dur - 0.5:.2f})\\,({dur:.2f}-t)/0.5\\,1))'"
        )
    elif animation == "slide_up":
        base += (
            f":y='if(lt(t\\,0.6)\\,h-((h-350)*t/0.6)\\,{y_pos})'"
        )
    else:
        base += f":y={y_pos}"

    return base


def _build_watermark_filter(fontsize: int) -> str:
    font_path = FONT_PATH.replace("\\", "/").replace(":", "\\:")
    escaped = _escape_drawtext("Created by Lungpee0945@gmail.com")
    return (
        f"drawtext=fontfile='{font_path}'"
        f":text='{escaped}'"
        f":fontsize={fontsize}"
        f":fontcolor=#000080"
        f":borderw=1"
        f":bordercolor=white@0.5"
        f":x=w-text_w-20"
        f":y=20"
    )


def _mix_with_bgm(narration_path: str, bgm_path: str, output_path: str,
                  volume: float = 0.2, duration: float = 0) -> str:
    if not duration:
        duration = get_audio_duration(narration_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fade_start = max(0, duration - 2)
    cmd = [
        FFMPEG, "-y",
        "-i", narration_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex",
        f"[1:a]volume={volume:.2f},afade=t=out:st={fade_start:.2f}:d=2[bgm];"
        f"[0:a][bgm]amix=inputs=2:duration=first:normalize=0[aout]",
        "-map", "[aout]",
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"BGM mix failed: {(result.stderr or '')[-300:]}")
        return narration_path
    return output_path


async def create_video(project_id: str, audio_path: str, script: str = "",
                       background_videos: list[str] | None = None,
                       background_images: list[str] | None = None,
                       subtitles: bool = True,
                       bgm_path: str = "", bgm_volume: float = 0.2,
                       aspect_ratio: str = "9:16",
                       mode: str = "narration",
                       overlay_opts: dict | None = None) -> str:
    cfg = ASPECT_CONFIGS.get(aspect_ratio, ASPECT_CONFIGS["9:16"])
    W, H = cfg["w"], cfg["h"]

    project_dir = os.path.join("projects", project_id)
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    ratio_tag = aspect_ratio.replace(":", "x")
    output_path = os.path.join(output_dir, f"final_{ratio_tag}.mp4")

    duration = get_audio_duration(audio_path)

    if bgm_path and os.path.exists(bgm_path):
        mixed_path = os.path.join(project_dir, "audio", "mixed.mp3")
        audio_path = _mix_with_bgm(audio_path, bgm_path, mixed_path,
                                    volume=bgm_volume, duration=duration)

    subtitle_filter = ""
    max_chars = cfg.get("sub_max_chars", 35)
    if subtitles:
        timing_path = os.path.join(project_dir, "audio", "dialogue_timing.json")
        if mode == "dialogue" and os.path.exists(timing_path):
            import json
            with open(timing_path, "r", encoding="utf-8") as f:
                timing = json.load(f)
            subtitle_filter = _build_dialogue_subtitle_filter(
                timing, fontsize=cfg["sub_fs"], y_expr=cfg["sub_y"],
                max_chars=max_chars)
        elif script:
            sections = _parse_script_sections(script)
            subtitle_filter = _build_subtitle_filter(
                sections, duration,
                fontsize=cfg["sub_fs"], y_expr=cfg["sub_y"],
                max_chars=max_chars)

    overlay_filter = ""
    opts = overlay_opts or {}
    overlay_fs = cfg.get("overlay_fs", 36)
    if opts.get("overlay_text"):
        overlay_filter = _build_overlay_text_filter(
            opts["overlay_text"], overlay_fs,
            opts.get("overlay_font", "sarabun"),
            opts.get("overlay_animation", "static"),
            duration)
    watermark_filter = _build_watermark_filter(overlay_fs // 2)

    extra_filters = ",".join(f for f in [overlay_filter, watermark_filter] if f)
    if extra_filters:
        subtitle_filter = (subtitle_filter + "," + extra_filters) if subtitle_filter else extra_filters

    videos = [v for v in (background_videos or []) if os.path.exists(v)]
    images = [img for img in (background_images or []) if os.path.exists(img)]

    if images and videos:
        converted = _convert_images_to_clips(images, duration, len(videos), cfg)
        ordered = []
        for v in videos:
            ordered.append((_extract_media_order(v), v))
        for img, conv in zip(images, converted):
            ordered.append((_extract_media_order(img), conv))
        ordered.sort(key=lambda x: x[0])
        all_clips = [clip for _, clip in ordered]
        return _create_video_with_clips(
            all_clips, audio_path, output_path, duration, subtitle_filter, cfg
        )

    if videos:
        return _create_video_with_clips(
            videos, audio_path, output_path, duration, subtitle_filter, cfg
        )

    if images and len(images) >= 2:
        return _create_video_with_images(
            images, audio_path, output_path, duration, subtitle_filter, cfg
        )

    bg_path = os.path.join(project_dir, f"background_{ratio_tag}.jpg")
    if not os.path.exists(bg_path):
        bg_path = os.path.join("assets", "templates", "default_bg.jpg")
    if not os.path.exists(bg_path):
        bg_path = os.path.join(project_dir, f"background_{ratio_tag}.jpg")
        _generate_gradient_bg(bg_path, f"{W}x{H}")

    vf_parts = [
        f"scale={W}:{H}:force_original_aspect_ratio=decrease",
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2",
        f"fps={cfg['fps']}",
        "format=yuv420p",
    ]
    if subtitle_filter:
        vf_parts.append(subtitle_filter)

    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", bg_path,
        "-i", audio_path,
        "-vf", ",".join(vf_parts),
        *_video_enc_args(),
        "-c:a", "aac", "-b:a", cfg["audio_br"], "-ar", "48000", "-ac", "2",
        "-t", f"{duration + 0.5:.2f}",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, timeout=300,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return output_path
        err = (result.stderr or "unknown error")[-1000:]
        raise RuntimeError(f"FFmpeg error: {err}")

    return output_path


def _convert_images_to_clips(images: list[str], total_duration: float,
                             num_videos: int, cfg: dict) -> list[str]:
    """Convert images to short video clips so they can be mixed with video clips."""
    W, H, FPS = cfg["w"], cfg["h"], cfg["fps"]
    total_segments = num_videos + len(images)
    seg_dur = total_duration / total_segments
    clips = []
    for i, img in enumerate(images):
        out_dir = os.path.dirname(img)
        clip_path = os.path.join(out_dir, f"img_clip_{i:02d}.mp4")
        cmd = [
            FFMPEG, "-y",
            "-loop", "1", "-t", f"{seg_dur + 1:.2f}", "-i", img,
            "-vf",
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={FPS},format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18",
            "-an", clip_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60,
                                encoding="utf-8", errors="replace")
        if result.returncode == 0 and os.path.exists(clip_path):
            clips.append(clip_path)
    return clips


def _create_video_with_clips(clips: list[str], audio_path: str,
                             output_path: str, duration: float,
                             subtitle_filter: str, cfg: dict) -> str:
    W, H, FPS = cfg["w"], cfg["h"], cfg["fps"]
    n = len(clips)

    filter_parts = []
    if n == 1:
        filter_parts.append(
            f"[0:v]trim=duration={duration:.2f},setpts=PTS-STARTPTS,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H},setsar=1,fps={FPS},format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration=1[merged]"
        )
    else:
        fade = XFADE_DUR
        seg_dur = (duration + (n - 1) * fade) / n
        for i in range(n):
            filter_parts.append(
                f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},setsar=1,fps={FPS},setpts=PTS-STARTPTS,"
                f"tpad=stop_mode=clone:stop_duration={seg_dur:.2f},"
                f"trim=duration={seg_dur:.2f},setpts=PTS-STARTPTS,"
                f"format=yuv420p[c{i}]"
            )
        prev = "c0"
        for i in range(n - 1):
            offset = (i + 1) * (seg_dur - fade)
            out_label = f"x{i}" if i < n - 2 else "xfinal"
            filter_parts.append(
                f"[{prev}][c{i+1}]xfade=transition=fade:duration={fade:.2f}"
                f":offset={offset:.2f}[{out_label}]"
            )
            prev = out_label
        filter_parts.append("[xfinal]format=yuv420p[merged]")

    if subtitle_filter:
        filter_parts.append(f"[merged]{subtitle_filter}[vout]")
        final_map = "[vout]"
    else:
        final_map = "[merged]"

    cmd = [FFMPEG, "-y"]
    for clip in clips:
        cmd.extend(["-i", clip])
    cmd.extend(["-i", audio_path])

    cmd.extend([
        "-filter_complex", ";".join(filter_parts),
        "-map", final_map,
        "-map", f"{n}:a",
        *_video_enc_args(),
        "-c:a", "aac", "-b:a", cfg["audio_br"], "-ar", "48000", "-ac", "2",
        "-t", f"{duration + 0.5:.2f}",
        "-movflags", "+faststart",
        output_path,
    ])

    result = subprocess.run(cmd, capture_output=True, timeout=600,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return output_path
        err = (result.stderr or "unknown error")[-500:]
        print(f"Video clips concat failed: {err}")
        print("Falling back to image slideshow or gradient")
        raise RuntimeError(f"FFmpeg clips error: {err}")

    return output_path


def _create_video_with_images(images: list[str], audio_path: str,
                              output_path: str, duration: float,
                              subtitle_filter: str, cfg: dict) -> str:
    W, H, FPS = cfg["w"], cfg["h"], cfg["fps"]
    pre_w, pre_h = cfg["pre_w"], cfg["pre_h"]
    n = len(images)

    filter_parts = []
    if n == 1:
        seg_dur = duration
        frames_per_seg = int(seg_dur * FPS)
    else:
        fade = XFADE_DUR
        seg_dur = (duration + (n - 1) * fade) / n
        frames_per_seg = int(seg_dur * FPS)

    for i in range(n):
        direction = i % 4
        if direction == 0:
            zoom = "min(zoom+0.0008\\,1.15)"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)"
        elif direction == 1:
            zoom = "if(eq(on\\,1)\\,1.15\\,max(zoom-0.0008\\,1.0))"
            x = "iw/2-(iw/zoom/2)"
            y = "ih/2-(ih/zoom/2)"
        elif direction == 2:
            zoom = "min(zoom+0.0008\\,1.15)"
            x = "0"
            y = "ih-ih/zoom"
        else:
            zoom = "min(zoom+0.0008\\,1.15)"
            x = "iw-iw/zoom"
            y = "0"

        filter_parts.append(
            f"[{i}:v]scale={pre_w}:{pre_h},zoompan=z='{zoom}'"
            f":x='{x}':y='{y}'"
            f":d={frames_per_seg}:s={W}x{H}:fps={FPS},format=yuv420p[v{i}]"
        )

    if n == 1:
        final_label = "vconcat"
        filter_parts.append(f"[v0]null[{final_label}]")
    else:
        prev = "v0"
        for i in range(n - 1):
            offset = (i + 1) * (seg_dur - fade)
            out_label = f"xi{i}" if i < n - 2 else "vcxfade"
            filter_parts.append(
                f"[{prev}][v{i+1}]xfade=transition=fade:duration={fade:.2f}"
                f":offset={offset:.2f}[{out_label}]"
            )
            prev = out_label
        filter_parts.append("[vcxfade]format=yuv420p[vconcat]")

    if subtitle_filter:
        filter_parts.append(f"[vconcat]{subtitle_filter}[vout]")
        final_map = "[vout]"
    else:
        final_map = "[vconcat]"

    cmd = [FFMPEG, "-y"]
    for img in images:
        cmd.extend(["-loop", "1", "-i", img])
    cmd.extend(["-i", audio_path])

    cmd.extend([
        "-filter_complex", ";".join(filter_parts),
        "-map", final_map,
        "-map", f"{n}:a",
        *_video_enc_args(),
        "-c:a", "aac", "-b:a", cfg["audio_br"], "-ar", "48000", "-ac", "2",
        "-t", f"{duration + 0.5:.2f}",
        "-movflags", "+faststart",
        output_path,
    ])

    result = subprocess.run(cmd, capture_output=True, timeout=600,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return output_path
        print("Ken Burns failed, falling back to simple slideshow")
        return _create_simple_slideshow(images, audio_path, output_path,
                                        duration, subtitle_filter, cfg)

    return output_path


def _create_simple_slideshow(images: list[str], audio_path: str,
                             output_path: str, duration: float,
                             subtitle_filter: str, cfg: dict) -> str:
    W, H, FPS = cfg["w"], cfg["h"], cfg["fps"]
    n = len(images)

    if n >= 2:
        fade = XFADE_DUR
        seg_dur = (duration + (n - 1) * fade) / n
    else:
        seg_dur = duration

    cmd = [FFMPEG, "-y"]
    for img in images:
        cmd.extend(["-loop", "1", "-t", f"{seg_dur:.2f}", "-i", img])
    cmd.extend(["-i", audio_path])

    filter_parts = []
    for i in range(n):
        filter_parts.append(
            f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p[s{i}]"
        )

    if n == 1:
        filter_parts.append(f"[s0]null[slideshow]")
    else:
        prev = "s0"
        for i in range(n - 1):
            offset = (i + 1) * (seg_dur - fade)
            out_label = f"ss{i}" if i < n - 2 else "ssxfade"
            filter_parts.append(
                f"[{prev}][s{i+1}]xfade=transition=fade:duration={fade:.2f}"
                f":offset={offset:.2f}[{out_label}]"
            )
            prev = out_label
        filter_parts.append("[ssxfade]format=yuv420p[slideshow]")

    if subtitle_filter:
        filter_parts.append(f"[slideshow]{subtitle_filter}[vout]")
        final_map = "[vout]"
    else:
        final_map = "[slideshow]"

    cmd.extend([
        "-filter_complex", ";".join(filter_parts),
        "-map", final_map,
        "-map", f"{n}:a",
        *_video_enc_args(),
        "-c:a", "aac", "-b:a", cfg["audio_br"], "-ar", "48000", "-ac", "2",
        "-t", f"{duration + 0.5:.2f}",
        "-movflags", "+faststart",
        output_path,
    ])

    result = subprocess.run(cmd, capture_output=True, timeout=600,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            return output_path
        err = (result.stderr or "unknown error")[-1000:]
        raise RuntimeError(f"FFmpeg slideshow error: {err}")

    return output_path


def _generate_gradient_bg(path: str, size: str = "1080x1920"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    h = size.split("x")[1]
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i",
        (
            f"gradients=s={size}:c0=#0f0c29:c1=#302b63:c2=#24243e"
            f":x0=0:y0=0:x1=0:y1={h}:duration=1:speed=0"
        ),
        "-frames:v", "1",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        _generate_solid_bg(path, size)


def _generate_solid_bg(path: str, size: str = "1080x1920"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i",
        f"color=c=0x0f0c29:s={size}:d=1",
        "-frames:v", "1",
        path,
    ]
    subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", check=True)
