import asyncio
import json
import os
import random
import re
import subprocess
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

from scripts.utils import get_audio_duration

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")
FONT_PATH = os.getenv("FONT_PATH", "F:/LocalAI/tools/fonts/Sarabun-Regular.ttf")
FONTS_DIR = os.path.dirname(FONT_PATH)
SUB_FONT = os.getenv("SUB_FONT", "Kanit")

FONT_MAP = {
    "sarabun": os.path.join(FONTS_DIR, "Sarabun-Regular.ttf"),
    "kanit": os.path.join(FONTS_DIR, "Kanit-Regular.ttf"),
}

XFADE_DUR = 0.5
TRANSITIONS = [
    "fade", "fadeblack", "fadewhite", "dissolve",
    "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "circleopen", "circleclose", "circlecrop", "rectcrop",
    "radial", "hblur",
    "diagtl", "diagtr", "diagbl", "diagbr",
    "hlslice", "hrslice", "vuslice", "vdslice",
]
_ENHANCE = "eq=contrast=1.05:brightness=0.02:saturation=1.1,unsharp=3:3:0.5:3:3:0.0"

LOUDNESS = "I=-14:TP=-1.5:LRA=11"

ASPECT_CONFIGS = {
    "9:16": {
        "w": 1080, "h": 1920, "fps": 30, "audio_br": "192k",
        "pre_w": 1920, "pre_h": 3412,
        "sub_fs": 66, "sub_margin": 260, "sub_max_chars": 26,
        "overlay_fs": 36,
    },
    "16:9": {
        "w": 1920, "h": 1080, "fps": 30, "audio_br": "192k",
        "pre_w": 3412, "pre_h": 1920,
        "sub_fs": 52, "sub_margin": 90, "sub_max_chars": 55,
        "overlay_fs": 32,
    },
}


# ── Encoder ──

_nvenc_ok: bool | None = None


def _check_nvenc() -> bool:
    """NVENC needs a driver new enough for this FFmpeg build; probe once with
    a real encode and fall back to x264 if it fails."""
    global _nvenc_ok
    if _nvenc_ok is None:
        try:
            r = subprocess.run(
                [FFMPEG, "-y", "-f", "lavfi", "-i", "color=s=256x256:d=0.2",
                 "-c:v", "h264_nvenc", "-f", "null", "-"],
                capture_output=True, timeout=20,
            )
            _nvenc_ok = r.returncode == 0
        except Exception:
            _nvenc_ok = False
        print(f"Video encoder: {'h264_nvenc (GPU)' if _nvenc_ok else 'libx264 (CPU) — NVENC unavailable'}")
    return _nvenc_ok


def _video_enc_args() -> list[str]:
    color = ["-color_range", "tv", "-colorspace", "bt709",
             "-color_primaries", "bt709", "-color_trc", "bt709"]
    if _check_nvenc():
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                "-rc", "vbr", "-cq", "21", "-b:v", "0",
                "-profile:v", "high", "-pix_fmt", "yuv420p", *color]
    return ["-c:v", "libx264", "-preset", "faster", "-crf", "20",
            "-profile:v", "high", "-pix_fmt", "yuv420p", *color]


def encoder_label() -> str:
    return "GPU (NVENC)" if _check_nvenc() else "CPU (x264)"


# ── Helpers ──

def _ff_path(path: str) -> str:
    """Path usable as a filter option value (relative when possible, so the
    Windows drive colon never needs escaping)."""
    try:
        path = os.path.relpath(path)
    except ValueError:
        pass
    path = path.replace("\\", "/")
    return "'" + path.replace(":", "\\:").replace("'", "\\'") + "'"


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def _get_video_stream_duration(path: str) -> float:
    ffprobe = os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe")
    r = subprocess.run(
        [ffprobe, "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "json", path],
        capture_output=True, text=True, timeout=30)
    try:
        return float(json.loads(r.stdout)["streams"][0]["duration"])
    except (ValueError, KeyError, IndexError, TypeError):
        return 0.0


def _extract_media_order(path: str) -> int:
    m = re.match(r"(\d+)_", os.path.basename(path))
    return int(m.group(1)) if m else 999


def _compute_segment_durations(n: int, total_duration: float, fade: float,
                               custom_durations: list[float] | None = None) -> list[float]:
    if not custom_durations or len(custom_durations) != n:
        if n == 1:
            return [total_duration]
        return [(total_duration + (n - 1) * fade) / n] * n
    auto_count = sum(1 for d in custom_durations if not d or d <= 0)
    fixed_total = sum(d for d in custom_durations if d and d > 0)
    remaining = total_duration + (n - 1) * fade - fixed_total
    auto_dur = max(2.0, remaining / auto_count) if auto_count else 0
    return [d if d and d > 0 else auto_dur for d in custom_durations]


# ── Subtitles (ASS via libass: HarfBuzz-shaped Thai, one filter for all cues) ──

_THAI_COMBINING = set("\u0E31" + "".join(chr(c) for c in range(0x0E34, 0x0E3B))
                      + "".join(chr(c) for c in range(0x0E47, 0x0E4F)))
_THAI_LEADING = set("\u0E40\u0E41\u0E42\u0E43\u0E44")


def _can_break_before(text: str, i: int) -> bool:
    return 0 < i < len(text) and text[i] not in _THAI_COMBINING \
        and text[i - 1] not in _THAI_LEADING


def _wrap_line(text: str, max_chars: int) -> list[str]:
    """Greedy wrap: prefer spaces; otherwise break between Thai character
    clusters (never before a vowel/tone mark or after a leading vowel)."""
    lines, rest = [], text.strip()
    while len(rest) > max_chars:
        cut = rest.rfind(" ", 0, max_chars + 1)
        if cut <= max_chars // 3:
            # Slightly long is better than splitting a phrase mid-way.
            cut = rest.find(" ", max_chars, int(max_chars * 1.2) + 1)
        if cut <= 0:
            # No dictionary: a leading vowel always starts a new syllable,
            # so breaking right before one rarely splits a word.
            window = range(max_chars, max(1, max_chars // 2), -1)
            cut = next((i for i in window if rest[i] in _THAI_LEADING), 0)
        if cut <= 0:
            cut = max_chars
            while cut > 1 and not _can_break_before(rest, cut):
                cut -= 1
        lines.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        lines.append(rest)
    return lines


def _proportional(entries: list[dict], start: float, end: float) -> list[dict]:
    total = sum(len(e["text"]) for e in entries) or 1
    t, out = start, []
    for e in entries:
        d = (end - start) * len(e["text"]) / total
        out.append({**e, "start": t, "end": t + d})
        t += d
    return out


def _load_timings(project_dir: str, script: str, duration: float) -> list[dict]:
    """Per-sentence subtitle cues. Times come from the TTS segments
    (audio/timings.json); text comes from the current script, so storyboard
    edits still show up. If the edit changed the sentence count, the edited
    text is spread proportionally over the speech."""
    from scripts.generate_audio import _clean_script_for_tts, _split_sentences, parse_dialogue

    timing = []
    for name in ("timings.json", "dialogue_timing.json"):
        path = os.path.join(project_dir, "audio", name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                timing = json.load(f)
            break

    if timing and "speaker" in timing[0]:
        entries = [{"text": d["text"], "speaker": d["speaker"]} for d in parse_dialogue(script)]
    else:
        entries = [{"text": s} for s in _split_sentences(_clean_script_for_tts(script))]
    entries = [e for e in entries if e["text"].strip()]

    if timing and len(entries) == len(timing):
        return [{**e, "start": t["start"], "end": t["end"]} for e, t in zip(entries, timing)]
    if timing and entries:
        return _proportional(entries, timing[0]["start"], timing[-1]["end"])
    if entries:
        return _proportional(entries, 0.0, duration)
    return []


def _ass_time(t: float) -> str:
    cs = int(round(max(0.0, t) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_text(text: str) -> str:
    return text.replace("\\", "/").replace("{", "(").replace("}", ")")


def _write_ass(timing: list[dict], cfg: dict, path: str):
    W, H = cfg["w"], cfg["h"]
    fs, margin = cfg["sub_fs"], cfg["sub_margin"]
    style = ("Style: {name},{font},{fs},{color},&H000000FF,&H00000000,&H64000000,"
             "0,0,0,0,100,100,0,0,1,4,1,2,60,60,{margin},1")
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style.format(name="A", font=SUB_FONT, fs=fs, color="&H00FFFFFF", margin=margin),
        style.format(name="B", font=SUB_FONT, fs=fs, color="&H0000D7FF", margin=margin),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for entry in timing:
        wrapped = _wrap_line(entry["text"], cfg["sub_max_chars"])
        cues = [wrapped[i:i + 2] for i in range(0, len(wrapped), 2)]
        start, end = float(entry["start"]), float(entry["end"])
        total_chars = sum(len("".join(c)) for c in cues) or 1
        t = start
        for cue in cues:
            cue_end = t + (end - start) * len("".join(cue)) / total_chars
            text = "\\N".join(_ass_text(c) for c in cue)
            lines.append(f"Dialogue: 0,{_ass_time(t)},{_ass_time(cue_end)},"
                         f"{entry.get('speaker', 'A')},,0,0,0,,{text}")
            t = cue_end
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")


# ── drawtext overlays (FFmpeg's drawtext shapes text with HarfBuzz) ──

def _escape_drawtext(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\u2019")
    text = text.replace('"', "\u201d")
    text = text.replace(":", "\\:")
    text = text.replace(";", "\\;")
    return text


def _drawtext_font(path: str) -> str:
    return path.replace("\\", "/").replace(":", "\\:")


def _build_overlay_text_filter(text: str, fontsize: int, font_name: str,
                               animation: str, duration: float) -> str:
    if not text.strip():
        return ""
    font_path = FONT_MAP.get(font_name, FONT_PATH)
    if not os.path.exists(font_path):
        font_path = FONT_PATH
    base = (
        f"drawtext=fontfile='{_drawtext_font(font_path)}'"
        f":text='{_escape_drawtext(text.strip())}'"
        f":expansion=none:fontsize={fontsize}:fontcolor=white"
        f":borderw=2:bordercolor=black@0.8:x=(w-text_w)/2"
    )
    y_pos = "h-350"
    if animation == "fade":
        fd = max(0.5, duration * 0.08)
        return base + (
            f":y={y_pos}:alpha='if(lt(t\\,{fd:.2f})\\,t/{fd:.2f}\\,"
            f"if(gt(t\\,{duration - fd:.2f})\\,({duration:.2f}-t)/{fd:.2f}\\,1))'"
        )
    if animation == "slide_up":
        sd = max(0.5, duration * 0.06)
        return base + f":y='if(lt(t\\,{sd:.2f})\\,h-((h-350)*t/{sd:.2f})\\,{y_pos})'"
    return base + f":y={y_pos}"


def _build_watermark_filter(fontsize: int) -> str:
    return (
        f"drawtext=fontfile='{_drawtext_font(FONT_PATH)}'"
        f":text='{_escape_drawtext('Created by Lungpee0945@gmail.com')}'"
        f":expansion=none:fontsize={fontsize}:fontcolor=#000080"
        f":borderw=1:bordercolor=white@0.5:x=w-text_w-20:y=20"
    )


# ── Audio: one mix + one two-pass loudness normalisation ──

def _audio_graph(has_bgm: bool, bgm_volume: float, duration: float) -> str:
    voice = "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"
    if not has_bgm:
        return voice + "[mix]"
    fade_start = max(0.0, duration - 2)
    return (
        f"{voice},asplit=2[v][vsc];"
        f"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"volume={bgm_volume:.2f},afade=t=out:st={fade_start:.2f}:d=2[bgm];"
        f"[bgm][vsc]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[duck];"
        f"[v][duck]amix=inputs=2:duration=first:normalize=0[mix]"
    )


def _finite(value) -> bool:
    try:
        return abs(float(value)) != float("inf")
    except (TypeError, ValueError):
        return False


def _prepare_final_audio(audio_path: str, bgm_path: str, bgm_volume: float,
                         duration: float, out_wav: str) -> str:
    """Voice (+ ducked BGM) normalised to -14 LUFS / -1.5 dBTP in two passes,
    so the only lossy step left is the AAC encode in the final mux."""
    has_bgm = bool(bgm_path) and os.path.exists(bgm_path)
    inputs = ["-i", audio_path] + (["-stream_loop", "-1", "-i", bgm_path] if has_bgm else [])
    graph = _audio_graph(has_bgm, bgm_volume, duration)

    measure = _run([FFMPEG, "-hide_banner", "-y", *inputs, "-filter_complex",
                    f"{graph};[mix]loudnorm={LOUDNESS}:print_format=json[out]",
                    "-map", "[out]", "-f", "null", "-"], timeout=300)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", measure.stderr or "", re.S)
    s = json.loads(m.group(0)) if m else {}
    if s and all(_finite(s.get(k)) for k in ("input_i", "input_tp", "input_lra", "input_thresh")):
        norm = (f"loudnorm={LOUDNESS}:measured_I={s['input_i']}:measured_TP={s['input_tp']}"
                f":measured_LRA={s['input_lra']}:measured_thresh={s['input_thresh']}"
                f":offset={s['target_offset']}:linear=true")
    else:
        norm = f"loudnorm={LOUDNESS}"
    result = _run([FFMPEG, "-y", *inputs, "-filter_complex",
                   f"{graph};[mix]{norm},aresample=48000[out]",
                   "-map", "[out]", "-c:a", "pcm_s16le", out_wav], timeout=300)
    if result.returncode != 0 or not os.path.exists(out_wav):
        raise RuntimeError(f"Audio mix failed: {(result.stderr or '')[-500:]}")
    return out_wav


# ── Video graphs ──

def _fit_blur(idx: str, W: int, H: int, FPS: int, p: str, still_frames: int = 0) -> str:
    """Scale to fit over a blurred fill of the same frame (no stretching/cropping).
    For stills (still_frames > 0) the chain runs once and the frame is looped."""
    chain = (
        f"[{idx}]split[bg{p}][fg{p}];"
        f"[bg{p}]scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},scale=iw/8:-1,scale={W}:{H}:flags=bilinear[blr{p}];"
        f"[fg{p}]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black@0[fpad{p}];"
        f"[blr{p}][fpad{p}]overlay=0:0,setsar=1,scale=out_range=tv,format=yuv420p,{_ENHANCE}"
    )
    if still_frames > 0:
        return chain + f",loop={still_frames}:1:0,fps={FPS}"
    return chain + f",fps={FPS}"


def _xfade_chain(labels: list[str], seg_durs: list[float], out: str) -> list[str]:
    if len(labels) == 1:
        return [f"[{labels[0]}]null[{out}]"]
    parts, prev, cumulative = [], labels[0], seg_durs[0]
    for i in range(len(labels) - 1):
        offset = cumulative - XFADE_DUR
        cumulative += seg_durs[i + 1] - XFADE_DUR
        label = f"xf{i}" if i < len(labels) - 2 else out
        parts.append(f"[{prev}][{labels[i + 1]}]xfade=transition={random.choice(TRANSITIONS)}"
                     f":duration={XFADE_DUR:.2f}:offset={offset:.2f}[{label}]")
        prev = label
    return parts


def _sequence_graph(sources: list[tuple[str, str]], seg_durs: list[float],
                    cfg: dict) -> tuple[list[str], list[str]]:
    """Clips and stills, in storyboard order, blur-fitted and crossfaded → [base]."""
    W, H, FPS = cfg["w"], cfg["h"], cfg["fps"]
    inputs, parts, labels = [], [], []
    for i, (path, kind) in enumerate(sources):
        if kind == "image":
            inputs += ["-i", path]
            frames = int((seg_durs[i] + 1) * FPS)
            parts.append(_fit_blur(f"{i}:v", W, H, FPS, f"m{i}", still_frames=frames)
                         + f",trim=duration={seg_durs[i]:.3f},setpts=PTS-STARTPTS[c{i}]")
        else:
            inputs += ["-stream_loop", "-1", "-i", path]
            parts.append(_fit_blur(f"{i}:v", W, H, FPS, f"m{i}")
                         + f",trim=duration={seg_durs[i]:.3f},setpts=PTS-STARTPTS[c{i}]")
        labels.append(f"c{i}")
    return inputs, parts + _xfade_chain(labels, seg_durs, "base")


def _kenburns_graph(images: list[str], seg_durs: list[float],
                    cfg: dict) -> tuple[list[str], list[str]]:
    """Stills with slow zoom/pan. zoompan runs at ~1.8x output size and is
    then downscaled, so its whole-pixel steps don't show as jitter."""
    W, H, FPS = cfg["w"], cfg["h"], cfg["fps"]
    PW, PH = cfg["pre_w"], cfg["pre_h"]
    moves = [
        ("min(zoom+0.0008\\,1.15)", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        ("if(lte(on\\,1)\\,1.15\\,max(zoom-0.0008\\,1.0))", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        ("min(zoom+0.0008\\,1.15)", "0", "ih-ih/zoom"),
        ("min(zoom+0.0008\\,1.15)", "iw-iw/zoom", "0"),
    ]
    inputs, parts, labels = [], [], []
    for i, img in enumerate(images):
        inputs += ["-i", img]
        z, x, y = moves[i % 4]
        frames = int(seg_durs[i] * FPS) + 1
        p = f"k{i}"
        parts.append(
            f"[{i}:v]split[bg{p}][fg{p}];"
            f"[bg{p}]scale={PW}:{PH}:force_original_aspect_ratio=increase,crop={PW}:{PH},"
            f"scale=iw/8:-1,scale={PW}:{PH}:flags=bilinear[blr{p}];"
            f"[fg{p}]scale={PW}:{PH}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={PW}:{PH}:(ow-iw)/2:(oh-ih)/2:color=black@0[fpad{p}];"
            f"[blr{p}][fpad{p}]overlay=0:0,setsar=1,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={PW}x{PH}:fps={FPS},"
            f"scale={W}:{H}:flags=lanczos:out_range=tv,format=yuv420p,{_ENHANCE},"
            f"trim=duration={seg_durs[i]:.3f},setpts=PTS-STARTPTS[c{i}]"
        )
        labels.append(f"c{i}")
    return inputs, parts + _xfade_chain(labels, seg_durs, "base")


def _render(inputs: list[str], parts: list[str], finish: list[str], extra_inputs: list[str],
            audio_wav: str, output_path: str, duration: float, cfg: dict) -> None:
    n_inputs = inputs.count("-i") + extra_inputs.count("-i")
    graph = parts + [f"[base]{','.join(finish)}[vout]" if finish else "[base]null[vout]"]
    timeout = int(max(600, duration * 20))
    for attempt in range(2):
        cmd = [FFMPEG, "-y", *inputs, *extra_inputs, "-i", audio_wav,
               "-filter_complex", ";".join(graph),
               "-map", "[vout]", "-map", f"{n_inputs}:a",
               *_video_enc_args(),
               "-c:a", "aac", "-b:a", cfg["audio_br"], "-ar", "48000", "-ac", "2",
               "-t", f"{duration + 0.3:.2f}", "-movflags", "+faststart",
               output_path]
        result = _run(cmd, timeout)
        if result.returncode == 0:
            return
        global _nvenc_ok
        if attempt == 0 and _nvenc_ok and "nvenc" in (result.stderr or "").lower():
            print("NVENC encode failed mid-render, retrying with libx264")
            _nvenc_ok = False
            continue
        if os.path.exists(output_path) and _get_video_stream_duration(output_path) >= duration * 0.95:
            return
        raise RuntimeError(f"FFmpeg render failed: {(result.stderr or 'unknown error')[-1000:]}")


def _apply_overlay_input(finish: list[str], extra_inputs: list[str], png: str, index: int):
    """Template chrome PNG overlaid inside the main graph (no second encode)."""
    extra_inputs += ["-i", png]
    current = ",".join(finish) if finish else "null"
    finish.clear()
    finish.append(f"{current}[pre];[pre][{index}:v]overlay=0:0:format=auto,"
                  f"scale=out_range=tv,format=yuv420p")


def _create_video_sync(project_id: str, audio_path: str, script: str,
                       background_videos: list[str], background_images: list[str],
                       subtitles: bool, bgm_path: str, bgm_volume: float,
                       aspect_ratio: str, overlay_opts: dict,
                       media_durations: list[float] | None,
                       log: Callable | None) -> str:
    cfg = ASPECT_CONFIGS.get(aspect_ratio, ASPECT_CONFIGS["9:16"])
    W, H = cfg["w"], cfg["h"]
    tag = aspect_ratio.replace(":", "x")
    project_dir = os.path.join("projects", project_id)
    output_dir = os.path.join(project_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"final_{tag}.mp4")

    if log:
        log(f"เข้ารหัสวิดีโอด้วย {encoder_label()}")
    duration = get_audio_duration(audio_path)
    final_audio = _prepare_final_audio(
        audio_path, bgm_path, bgm_volume, duration,
        os.path.join(project_dir, "audio", f"final_mix_{tag}.wav"))

    finish: list[str] = []
    if subtitles:
        timing = _load_timings(project_dir, script, duration)
        if timing:
            ass_path = os.path.join(output_dir, f"subs_{tag}.ass")
            _write_ass(timing, cfg, ass_path)
            finish.append(f"subtitles=filename={_ff_path(ass_path)}:fontsdir={_ff_path(FONTS_DIR)}")
    if overlay_opts.get("overlay_text"):
        finish.append(_build_overlay_text_filter(
            overlay_opts["overlay_text"], cfg["overlay_fs"],
            overlay_opts.get("overlay_font", "sarabun"),
            overlay_opts.get("overlay_animation", "static"), duration))
    finish.append(_build_watermark_filter(cfg["overlay_fs"] // 2))

    videos = [v for v in background_videos if os.path.exists(v)]
    images = [i for i in background_images if os.path.exists(i)]
    sources = sorted([(v, "video") for v in videos] + [(i, "image") for i in images],
                     key=lambda s: _extract_media_order(s[0]))
    stills_only = bool(sources) and not videos
    if not sources:
        bg = os.path.join("assets", "templates", "default_bg.jpg")
        sources = [(bg, "image")]
        media_durations = None
    seg_durs = _compute_segment_durations(len(sources), duration, XFADE_DUR, media_durations)

    extra_inputs: list[str] = []
    n_media = len(sources)
    if overlay_opts.get("template_id") == "social_repost" and overlay_opts.get("template_fields"):
        from scripts.image_templates import render_social_repost_overlay
        fields = overlay_opts["template_fields"]
        png = os.path.join(output_dir, f"template_{tag}_overlay.png")
        render_social_repost_overlay(
            png, w=W, h=H,
            headline=fields.get("headline", ""),
            channel_name=fields.get("channel_name", ""),
            verified=bool(fields.get("verified")),
            like_count=fields.get("like_count", ""),
            comment_count=fields.get("comment_count", ""),
            share_count=fields.get("share_count", ""),
            caption=fields.get("caption", ""),
        )
        _apply_overlay_input(finish, extra_inputs, png, n_media)

    if stills_only:
        inputs, parts = _kenburns_graph([p for p, _ in sources], seg_durs, cfg)
        try:
            _render(inputs, parts, finish, extra_inputs, final_audio, output_path, duration, cfg)
            return output_path
        except RuntimeError as e:
            print(f"Ken Burns render failed, using static slideshow: {str(e)[-300:]}")
            if log:
                log("Ken Burns ล้มเหลว — ใช้สไลด์โชว์แบบนิ่งแทน", "warning")

    inputs, parts = _sequence_graph(sources, seg_durs, cfg)
    _render(inputs, parts, finish, extra_inputs, final_audio, output_path, duration, cfg)
    return output_path


async def create_video(project_id: str, audio_path: str, script: str = "",
                       background_videos: list[str] | None = None,
                       background_images: list[str] | None = None,
                       subtitles: bool = True,
                       bgm_path: str = "", bgm_volume: float = 0.2,
                       aspect_ratio: str = "9:16",
                       overlay_opts: dict | None = None,
                       media_durations: list[float] | None = None,
                       log: Callable | None = None) -> str:
    return await asyncio.to_thread(
        _create_video_sync, project_id, audio_path, script,
        background_videos or [], background_images or [],
        subtitles, bgm_path, bgm_volume, aspect_ratio, overlay_opts or {},
        media_durations, log,
    )
