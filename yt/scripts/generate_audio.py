import os
import re
import json
import asyncio
import edge_tts
from pathlib import Path
from scripts.utils import get_audio_duration

_ENV_DIR = Path(__file__).resolve().parent.parent

FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")

VOICES = {
    "female": "th-TH-PremwadeeNeural",
    "male": "th-TH-NiwatNeural",
}

TONE_PRESETS = {
    "normal": {"base_rate": 0, "base_pitch": 0, "variation": 0},
    "cheerful": {"base_rate": 5, "base_pitch": 10, "variation": 20},
    "serious": {"base_rate": -8, "base_pitch": -8, "variation": 12},
    "energetic": {"base_rate": 12, "base_pitch": 8, "variation": 25},
    "warm": {"base_rate": -5, "base_pitch": 5, "variation": 15},
    "news": {"base_rate": 5, "base_pitch": -3, "variation": 18},
}


def load_replacements() -> dict:
    path = _ENV_DIR / "config" / "replacements.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _clean_script_for_tts(text: str) -> str:
    lines = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"\[.*?\]", "", line).strip()
        cleaned = re.sub(r"^[—\-–]+\s*", "", cleaned).strip()
        cleaned = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", cleaned)
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def apply_replacements(text: str, replacements: dict) -> str:
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
    for eng in sorted_keys:
        thai = replacements[eng]
        pattern = r"(?<![A-Za-z])" + re.escape(eng) + r"(?![A-Za-z])"
        text = re.sub(pattern, thai, text, flags=re.IGNORECASE)
    return text


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?。！？])\s*', text)
    if len(parts) <= 1:
        parts = text.strip().split("\n")
    sentences = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if sentences and len(sentences[-1]) < 15 and len(p) < 15:
            sentences[-1] += " " + p
        else:
            sentences.append(p)
    return sentences if sentences else [text]


def _calc_sentence_prosody(idx: int, total: int, sent: str,
                           base_rate: int, base_pitch: int,
                           preset: dict) -> tuple[str, str]:
    var = preset["variation"]
    patterns = [0.6, -0.3, 0.2, -0.5, 0.4, -0.2, 0.5, -0.4]
    r_offset = int(var * patterns[idx % len(patterns)])
    p_offset = int(var * patterns[(idx + 2) % len(patterns)])

    if sent.rstrip().endswith("?") or sent.rstrip().endswith("？"):
        p_offset += int(var * 0.8)
        r_offset -= int(var * 0.3)
    elif sent.rstrip().endswith("!") or sent.rstrip().endswith("！"):
        r_offset += int(var * 0.5)
        p_offset += int(var * 0.4)

    if idx == 0:
        r_offset += int(var * 0.4)
        p_offset += int(var * 0.5)
    elif idx == total - 1:
        r_offset -= int(var * 0.3)
        p_offset -= int(var * 0.2)

    r_val = max(-50, min(50, base_rate + r_offset))
    p_val = max(-50, min(50, base_pitch + p_offset))
    r_str = f"+{r_val}%" if r_val >= 0 else f"{r_val}%"
    p_str = f"+{p_val}Hz" if p_val >= 0 else f"{p_val}Hz"
    return r_str, p_str


async def _tts_with_retry(text: str, voice: str, output_path: str,
                          rate: str, pitch: str, max_retries: int = 5,
                          tone: str = "normal"):
    last_err = None
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            await communicate.save(output_path)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                return
        except (edge_tts.exceptions.NoAudioReceived, Exception) as e:
            last_err = e
        wait = 2 ** attempt
        print(f"edge-tts retry {attempt + 1}/{max_retries} (wait {wait}s)")
        await asyncio.sleep(wait)
    raise last_err or edge_tts.exceptions.NoAudioReceived("TTS failed after retries")


async def _generate_toned_narration(
    project_id: str, text: str, voice_name: str,
    base_rate: str, base_pitch: str, tone: str,
) -> str:
    import subprocess

    preset = TONE_PRESETS.get(tone, TONE_PRESETS["normal"])
    output_dir = os.path.join("projects", project_id, "audio")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "narration.mp3")

    if preset["variation"] == 0:
        await _tts_with_retry(text, voice_name, output_path, base_rate, base_pitch)
        return output_path

    sentences = _split_sentences(text)
    if len(sentences) <= 1:
        await _tts_with_retry(text, voice_name, output_path, base_rate, base_pitch)
        return output_path

    base_r = int(re.search(r'[+-]?\d+', base_rate).group()) if re.search(r'[+-]?\d+', base_rate) else 0
    base_p = int(re.search(r'[+-]?\d+', base_pitch).group()) if re.search(r'[+-]?\d+', base_pitch) else 0
    base_r += preset["base_rate"]
    base_p += preset["base_pitch"]

    clips_dir = os.path.join(output_dir, "tone_clips")
    os.makedirs(clips_dir, exist_ok=True)

    clip_paths = []
    for i, sent in enumerate(sentences):
        r_str, p_str = _calc_sentence_prosody(i, len(sentences), sent, base_r, base_p, preset)
        clip_path = os.path.join(clips_dir, f"sent_{i:03d}.mp3")
        print(f"  sentence {i+1}/{len(sentences)}: rate={r_str} pitch={p_str}")
        await _tts_with_retry(sent, voice_name, clip_path, r_str, p_str)
        clip_paths.append(clip_path)
        if i < len(sentences) - 1:
            await asyncio.sleep(0.15)

    gap_seconds = 0.15
    inputs = []
    filter_parts = []
    for i, clip in enumerate(clip_paths):
        inputs.extend(["-i", clip])
        filter_parts.append(f"[{i}:a]aresample=24000,aformat=sample_fmts=fltp:channel_layouts=mono[a{i}]")

    concat_parts = []
    for i in range(len(clip_paths)):
        concat_parts.append(f"[a{i}]")
        if i < len(clip_paths) - 1:
            filter_parts.append(
                f"aevalsrc=0:s=24000:d={gap_seconds}:c=mono,aformat=sample_fmts=fltp:channel_layouts=mono[gap{i}]"
            )
            concat_parts.append(f"[gap{i}]")

    n_segments = len(clip_paths) + len(clip_paths) - 1
    filter_parts.append("".join(concat_parts) + f"concat=n={n_segments}:v=0:a=1[out]")

    cmd = [FFMPEG, "-y"] + inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, timeout=120,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        err = (result.stderr or "")[-500:]
        raise RuntimeError(f"Toned narration concat failed: {err}")

    return output_path


def parse_dialogue(script: str) -> list[dict]:
    """Parse A:/B: dialogue format into list of {speaker, text}."""
    lines = []
    for raw in script.strip().split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r"^([AB])\s*[:：]\s*(.+)", raw)
        if m:
            text = m.group(2).strip()
            text = re.sub(r"\[.*?\]", "", text).strip()
            text = re.sub(r"^[—\-–]+\s*", "", text).strip()
            text = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", text)
            if text:
                lines.append({"speaker": m.group(1), "text": text})
        else:
            cleaned = re.sub(r"\[.*?\]", "", raw).strip()
            cleaned = re.sub(r"^[—\-–]+\s*", "", cleaned).strip()
            cleaned = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", cleaned)
            if cleaned and len(cleaned) > 3:
                speaker = "A" if len(lines) % 2 == 0 else "B"
                lines.append({"speaker": speaker, "text": cleaned})
    return lines


async def _generate_dialogue_audio(
    project_id: str, script: str,
    voice_a: str, voice_b: str,
    rate: str, pitch: str,
    replacements: dict,
    tone: str = "normal",
) -> str:
    """Generate multi-voice dialogue audio with per-line TTS."""
    output_dir = os.path.join("projects", project_id, "audio")
    os.makedirs(output_dir, exist_ok=True)

    lines = parse_dialogue(script)
    if not lines:
        raise ValueError("No dialogue lines found in script")

    voice_map = {"A": voice_a, "B": voice_b}
    gap_seconds = 0.3
    clips_dir = os.path.join(output_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    preset = TONE_PRESETS.get(tone, TONE_PRESETS["normal"])
    base_r = int(re.search(r'[+-]?\d+', rate).group()) if re.search(r'[+-]?\d+', rate) else 0
    base_p = int(re.search(r'[+-]?\d+', pitch).group()) if re.search(r'[+-]?\d+', pitch) else 0
    base_r += preset["base_rate"]
    base_p += preset["base_pitch"]

    clip_paths = []
    for i, line in enumerate(lines):
        processed = apply_replacements(line["text"], replacements)
        voice_name = voice_map[line["speaker"]]
        clip_path = os.path.join(clips_dir, f"line_{i:03d}.mp3")
        if preset["variation"] > 0:
            r_str, p_str = _calc_sentence_prosody(i, len(lines), processed, base_r, base_p, preset)
        else:
            r_str, p_str = rate, pitch
        await _tts_with_retry(processed, voice_name, clip_path, r_str, p_str)
        clip_paths.append(clip_path)
        if i < len(lines) - 1:
            await asyncio.sleep(0.2)

    timing = []
    current_time = 0.0
    for i, line in enumerate(lines):
        dur = get_audio_duration(clip_paths[i])
        timing.append({
            "speaker": line["speaker"],
            "text": line["text"],
            "start": round(current_time, 3),
            "end": round(current_time + dur, 3),
        })
        current_time += dur + gap_seconds

    timing_path = os.path.join(output_dir, "dialogue_timing.json")
    with open(timing_path, "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)

    output_path = os.path.join(output_dir, "narration.mp3")

    if len(clip_paths) == 1:
        import shutil
        shutil.copy2(clip_paths[0], output_path)
        return output_path

    inputs = []
    filter_parts = []
    idx = 0
    for i, clip in enumerate(clip_paths):
        inputs.extend(["-i", clip])
        filter_parts.append(f"[{idx}:a]aresample=24000,aformat=sample_fmts=fltp:channel_layouts=mono[a{idx}]")
        idx += 1

    concat_parts = []
    for i in range(len(clip_paths)):
        concat_parts.append(f"[a{i}]")
        if i < len(clip_paths) - 1:
            gap_samples = int(gap_seconds * 24000)
            filter_parts.append(
                f"aevalsrc=0:s=24000:d={gap_seconds}:c=mono,aformat=sample_fmts=fltp:channel_layouts=mono[gap{i}]"
            )
            concat_parts.append(f"[gap{i}]")

    n_segments = len(clip_paths) + len(clip_paths) - 1
    filter_parts.append("".join(concat_parts) + f"concat=n={n_segments}:v=0:a=1[out]")

    cmd = [FFMPEG, "-y"] + inputs + [
        "-filter_complex", ";".join(filter_parts),
        "-map", "[out]",
        "-c:a", "libmp3lame", "-q:a", "2",
        output_path,
    ]

    import subprocess
    result = subprocess.run(cmd, capture_output=True, timeout=120,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        err = (result.stderr or "")[-500:]
        raise RuntimeError(f"Dialogue concat failed: {err}")

    return output_path


async def generate_audio(
    project_id: str,
    script: str,
    voice: str = "female",
    rate: str = "+0%",
    pitch: str = "+0Hz",
    clone_voice_id: str = "",
    mode: str = "narration",
    voice_b: str = "",
    tone: str = "normal",
) -> str:
    replacements = load_replacements()

    if mode == "dialogue":
        voice_a_name = VOICES.get(voice, VOICES["female"])
        if not voice_b:
            voice_b = "male" if voice == "female" else "female"
        voice_b_name = VOICES.get(voice_b, VOICES["male"])
        return await _generate_dialogue_audio(
            project_id, script, voice_a_name, voice_b_name,
            rate, pitch, replacements, tone=tone,
        )

    processed = _clean_script_for_tts(script)
    processed = apply_replacements(processed, replacements)

    voice_name = VOICES.get(voice, VOICES["female"])

    output_dir = os.path.join("projects", project_id, "audio")
    os.makedirs(output_dir, exist_ok=True)

    if clone_voice_id:
        base_path = os.path.join(output_dir, "base_tts.mp3")
        if tone != "normal":
            await _generate_toned_narration(project_id, processed, voice_name, rate, pitch, tone)
            import shutil
            shutil.move(os.path.join(output_dir, "narration.mp3"), base_path)
        else:
            await _tts_with_retry(processed, voice_name, base_path, rate, pitch)

        from scripts.voice_clone import clone_voice, get_reference_path
        ref_path = get_reference_path(clone_voice_id)
        if ref_path:
            output_path = os.path.join(output_dir, "narration.wav")
            await clone_voice(base_path, ref_path, output_path)
        else:
            output_path = os.path.join(output_dir, "narration.mp3")
            os.rename(base_path, output_path)
    else:
        if tone != "normal":
            output_path = await _generate_toned_narration(
                project_id, processed, voice_name, rate, pitch, tone)
        else:
            output_path = os.path.join(output_dir, "narration.mp3")
            await _tts_with_retry(processed, voice_name, output_path, rate, pitch)

    return output_path
