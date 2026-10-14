import os
import re
import json
import time
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Callable

import edge_tts

from scripts.utils import get_audio_duration

_ENV_DIR = Path(__file__).resolve().parent.parent

FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")

VOICES = {
    "female": "th-TH-PremwadeeNeural",
    "male": "th-TH-NiwatNeural",
}

TONE_PRESETS = {
    "normal": {"base_rate": 0, "base_pitch": 0, "variation": 0},
    "cheerful": {"base_rate": 3, "base_pitch": 5, "variation": 8},
    "serious": {"base_rate": -5, "base_pitch": -5, "variation": 5},
    "energetic": {"base_rate": 8, "base_pitch": 5, "variation": 10},
    "warm": {"base_rate": -3, "base_pitch": 3, "variation": 6},
    "news": {"base_rate": 3, "base_pitch": -2, "variation": 7},
}

TTS_CONCURRENCY = 3
NARRATION_GAP = 0.15
DIALOGUE_GAP = 0.3


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
        cleaned = re.sub(r"[.]{3,}", "...", cleaned)
        cleaned = re.sub(r"[!]{2,}", "!", cleaned)
        cleaned = re.sub(r"[?]{2,}", "?", cleaned)
        cleaned = re.sub(r"[#~_=|<>^]{2,}", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned and not re.fullmatch(r"[.\-–—!?…\s]+", cleaned):
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
    parts = re.split(r'(?<=[.!?。！？])\s*|\n+', text)
    sentences = []
    for p in parts:
        p = (p or "").strip()
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

    return _fmt_rate(base_rate + r_offset), _fmt_pitch(base_pitch + p_offset)


def _parse_signed(value: str) -> int:
    m = re.search(r"[+-]?\d+", value or "")
    return int(m.group()) if m else 0


def _fmt_rate(v: int) -> str:
    v = max(-50, min(50, v))
    return f"+{v}%" if v >= 0 else f"{v}%"


def _fmt_pitch(v: int) -> str:
    v = max(-50, min(50, v))
    return f"+{v}Hz" if v >= 0 else f"{v}Hz"


def _strip_tts_noise(text: str) -> str:
    clean = re.sub(r"[.]{3,}", "...", text)
    clean = re.sub(r"[!]{2,}", "!", clean)
    clean = re.sub(r"[?]{2,}", "?", clean)
    return re.sub(r"[#~_=|<>^]{2,}", "", clean).strip()


def _has_speech(text: str) -> bool:
    return bool(text) and not re.fullmatch(r"[.\-–—!?…\s]+", text)


def _write_silence(path: str, seconds: float = 0.3):
    codec = ["-c:a", "pcm_s16le"] if path.endswith(".wav") else ["-c:a", "libmp3lame", "-q:a", "2"]
    subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                    "-t", f"{seconds}", *codec, path],
                   capture_output=True, timeout=30)


# ── edge-tts with circuit breaker ──
# gTTS ignores voice/rate/pitch/tone, so staying on it degrades every setting.
# Pause edge-tts briefly after repeated failures, then let it prove itself again.

class EdgeTTSUnavailable(Exception):
    pass


_edge_tts_failures = 0
_edge_tts_blocked_until = 0.0
EDGE_TTS_COOLDOWN = 120


async def _edge_tts(text: str, voice: str, output_path: str,
                    rate: str, pitch: str, max_retries: int = 5):
    # The service intermittently answers "No audio received" (~1 in 4 calls
    # in testing, independent of text/prosody), so a few quick retries matter.
    global _edge_tts_failures, _edge_tts_blocked_until
    if time.monotonic() < _edge_tts_blocked_until:
        raise EdgeTTSUnavailable("edge-tts cooling down")
    voice_name = VOICES.get(voice, voice)
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice_name, rate=rate, pitch=pitch)
            await asyncio.wait_for(communicate.save(output_path), timeout=30)
            if os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                _edge_tts_failures = 0
                _edge_tts_blocked_until = 0.0
                return
        except asyncio.TimeoutError:
            print(f"edge-tts timeout on attempt {attempt + 1}/{max_retries}")
        except Exception as e:
            print(f"edge-tts error on attempt {attempt + 1}/{max_retries}: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(min(1.5 * (attempt + 1), 5))
    _edge_tts_failures += 1
    if _edge_tts_failures >= 3:
        _edge_tts_blocked_until = time.monotonic() + EDGE_TTS_COOLDOWN
        print(f"edge-tts paused for {EDGE_TTS_COOLDOWN}s after {_edge_tts_failures} failures")
    raise EdgeTTSUnavailable("edge-tts failed")


def _gtts_sync(text: str, output_path: str):
    from gtts import gTTS
    gTTS(text=text, lang="th").save(output_path)
    if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
        raise RuntimeError("gTTS produced empty audio")


async def _tts_with_retry(text: str, voice: str, output_path: str,
                          rate: str, pitch: str, max_retries: int = 5):
    """Single-shot TTS for previews/comparisons: edge-tts, gTTS if unavailable."""
    clean = _strip_tts_noise(text)
    if not _has_speech(clean):
        await asyncio.to_thread(_write_silence, output_path)
        return
    try:
        await _edge_tts(clean, voice, output_path, rate, pitch, max_retries)
    except EdgeTTSUnavailable:
        print("edge-tts unavailable, using gTTS (voice/rate/pitch will not apply)")
        await asyncio.to_thread(_gtts_sync, clean, output_path)


async def _synthesize_segments(segments: list[dict], seg_dir: str,
                               log: Callable | None = None) -> list[str]:
    """TTS every segment (3 at a time). If edge-tts fails for any of them, the
    whole set is redone with gTTS so one clip never mixes two different voices."""
    os.makedirs(seg_dir, exist_ok=True)
    paths = [os.path.join(seg_dir, f"seg_{i:03d}.mp3") for i in range(len(segments))]
    sem = asyncio.Semaphore(TTS_CONCURRENCY)

    async def one(i: int):
        seg = segments[i]
        text = _strip_tts_noise(seg["tts_text"])
        if not _has_speech(text):
            await asyncio.to_thread(_write_silence, paths[i])
            return
        async with sem:
            await _edge_tts(text, seg["voice"], paths[i], seg["rate"], seg["pitch"])

    results = await asyncio.gather(*(one(i) for i in range(len(segments))),
                                   return_exceptions=True)
    errors = [r for r in results if isinstance(r, Exception)]
    if not errors:
        return paths
    if not all(isinstance(e, EdgeTTSUnavailable) for e in errors):
        raise next(e for e in errors if not isinstance(e, EdgeTTSUnavailable))

    msg = "edge-tts ใช้ไม่ได้ — สร้างเสียงทั้งหมดใหม่ด้วย gTTS (เสียง/ความเร็ว/โทนจะไม่ตรงที่เลือก)"
    print(msg)
    if log:
        log(msg, "warning")

    def redo_all():
        for i, seg in enumerate(segments):
            text = _strip_tts_noise(seg["tts_text"])
            if _has_speech(text):
                _gtts_sync(text, paths[i])
            else:
                _write_silence(paths[i])
    await asyncio.to_thread(redo_all)
    return paths


def _concat_with_gaps(clips: list[str], gap: float, output_wav: str) -> list[float]:
    """Join clips into one 48 kHz mono WAV with silence between them; returns each clip's duration."""
    durations = [get_audio_duration(c) for c in clips]
    inputs, filters, labels = [], [], []
    for i, clip in enumerate(clips):
        inputs += ["-i", clip]
        filters.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[a{i}]")
        labels.append(f"[a{i}]")
        if i < len(clips) - 1:
            filters.append(f"aevalsrc=0:s=48000:d={gap}:c=mono,"
                           f"aformat=sample_fmts=fltp:channel_layouts=mono[g{i}]")
            labels.append(f"[g{i}]")
    filters.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1[out]")
    cmd = [FFMPEG, "-y", *inputs, "-filter_complex", ";".join(filters),
           "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "48000", output_wav]
    result = subprocess.run(cmd, capture_output=True, timeout=300,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0 or not os.path.exists(output_wav):
        raise RuntimeError(f"Audio concat failed: {(result.stderr or '')[-500:]}")
    return durations


def _write_timings(path: str, items: list[dict], durations: list[float], gap: float):
    timing, t = [], 0.0
    for it, d in zip(items, durations):
        entry = {"text": it["text"], "start": round(t, 3), "end": round(t + d, 3)}
        if "speaker" in it:
            entry["speaker"] = it["speaker"]
        timing.append(entry)
        t += d + gap
    with open(path, "w", encoding="utf-8") as f:
        json.dump(timing, f, ensure_ascii=False, indent=2)


def _write_proportional_timings(path: str, items: list[dict], total: float):
    """For engines that synthesize everything in one pass (F5): spread time by text length."""
    weights = [max(1, len(it["text"])) for it in items]
    scale = total / sum(weights)
    _write_timings(path, items, [w * scale for w in weights], 0.0)


def _polish_audio(wav_path: str):
    """Clean up cloned voice: rumble cut, gentle compression, clarity EQ.
    Loudness is normalised once, at the final video mux."""
    polished = wav_path.replace(".wav", "_polished.wav")
    af = ",".join([
        "highpass=f=80",
        "acompressor=threshold=-20dB:ratio=2:attack=5:release=80",
        "equalizer=f=2500:t=q:w=1.2:g=2",
        "equalizer=f=180:t=q:w=0.8:g=-1",
    ])
    result = subprocess.run([FFMPEG, "-y", "-i", wav_path, "-af", af,
                             "-c:a", "pcm_s16le", "-ar", "48000", polished],
                            capture_output=True, timeout=180)
    if result.returncode == 0 and os.path.exists(polished) and os.path.getsize(polished) > 100:
        os.replace(polished, wav_path)
    else:
        print("Clone polish failed, using raw clone output")


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
    clone_tau: float = 0.3,
    clone_engine: str = "openvoice",
    tone_preset: dict | None = None,
    log: Callable | None = None,
) -> str:
    """Returns path to audio/narration.wav and writes audio/timings.json
    (one entry per spoken sentence/line) for subtitle timing."""
    replacements = load_replacements()
    out_dir = os.path.join("projects", project_id, "audio")
    seg_dir = os.path.join(out_dir, "segments")
    os.makedirs(out_dir, exist_ok=True)
    shutil.rmtree(seg_dir, ignore_errors=True)
    narration = os.path.join(out_dir, "narration.wav")
    timings_path = os.path.join(out_dir, "timings.json")

    preset = tone_preset or TONE_PRESETS.get(tone, TONE_PRESETS["normal"])
    base_r = _parse_signed(rate) + preset["base_rate"]
    base_p = _parse_signed(pitch) + preset["base_pitch"]

    if mode == "dialogue":
        lines = parse_dialogue(script)
        if not lines:
            raise ValueError("No dialogue lines found in script")
        vb = voice_b or ("male" if voice == "female" else "female")
        voice_map = {"A": VOICES.get(voice, VOICES["female"]), "B": VOICES.get(vb, VOICES["male"])}
        items = [{"text": ln["text"], "speaker": ln["speaker"], "voice": voice_map[ln["speaker"]]}
                 for ln in lines]
        gap = DIALOGUE_GAP
    else:
        sentences = _split_sentences(_clean_script_for_tts(script))
        items = [{"text": s, "voice": VOICES.get(voice, VOICES["female"])} for s in sentences]
        gap = NARRATION_GAP

    if clone_voice_id and clone_engine == "f5-tts-thai" and mode != "dialogue":
        from scripts.voice_clone import get_reference_path
        from scripts.f5_clone import clone_with_f5, is_f5_available
        ref_path = get_reference_path(clone_voice_id)
        if ref_path and is_f5_available():
            full_text = apply_replacements("\n".join(it["text"] for it in items), replacements)
            try:
                await clone_with_f5(full_text, ref_path, narration)
                await asyncio.to_thread(_polish_audio, narration)
                total = await asyncio.to_thread(get_audio_duration, narration)
                _write_proportional_timings(timings_path, items, total)
                return narration
            except Exception as e:
                msg = f"F5-TTS-THAI ล้มเหลว ({str(e)[:120]}) — ใช้ OpenVoice แทน"
                print(msg)
                if log:
                    log(msg, "warning")

    segments = []
    for i, it in enumerate(items):
        if preset["variation"] > 0:
            r, p = _calc_sentence_prosody(i, len(items), it["text"], base_r, base_p, preset)
        else:
            r, p = _fmt_rate(base_r), _fmt_pitch(base_p)
        segments.append({"tts_text": apply_replacements(it["text"], replacements),
                         "voice": it["voice"], "rate": r, "pitch": p})

    clip_paths = await _synthesize_segments(segments, seg_dir, log=log)
    base_wav = os.path.join(out_dir, "base_tts.wav") if clone_voice_id else narration
    durations = await asyncio.to_thread(_concat_with_gaps, clip_paths, gap, base_wav)
    _write_timings(timings_path, items, durations, gap)
    shutil.rmtree(seg_dir, ignore_errors=True)

    if clone_voice_id:
        from scripts.voice_clone import clone_voice, get_reference_path
        ref_path = get_reference_path(clone_voice_id)
        cloned = False
        if ref_path:
            cloned = await clone_voice(base_wav, ref_path, narration, tau=clone_tau)
        if cloned:
            await asyncio.to_thread(_polish_audio, narration)
        else:
            os.replace(base_wav, narration)
            msg = "โคลนเสียงไม่สำเร็จ — ใช้เสียง TTS ปกติแทน"
            print(msg)
            if log:
                log(msg, "warning")
        if os.path.exists(base_wav):
            os.remove(base_wav)

    return narration
