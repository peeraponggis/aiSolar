import json
import os
import uuid
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VOICES_DIR = BASE_DIR / "voices"
VENV_PYTHON = str(BASE_DIR / ".venv-clone" / "Scripts" / "python.exe")


def _ensure_dirs():
    VOICES_DIR.mkdir(exist_ok=True)


def list_voice_profiles() -> list[dict]:
    _ensure_dirs()
    profiles = []
    for d in sorted(VOICES_DIR.iterdir()):
        meta_path = d / "metadata.json"
        if d.is_dir() and meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta["id"] = d.name
                profiles.append(meta)
            except Exception:
                pass
    return profiles


def get_reference_path(voice_id: str) -> str | None:
    profile_dir = VOICES_DIR / voice_id
    for ext in (".wav", ".mp3", ".m4a", ".ogg", ".flac"):
        ref = profile_dir / f"reference{ext}"
        if ref.exists():
            return str(ref)
    return None


def save_voice_profile(audio_bytes: bytes, filename: str, name: str) -> dict:
    _ensure_dirs()
    voice_id = uuid.uuid4().hex[:8]
    profile_dir = VOICES_DIR / voice_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower() or ".wav"
    raw_path = profile_dir / f"upload_raw{ext}"
    with open(raw_path, "wb") as f:
        f.write(audio_bytes)

    # OpenVoice's se_extractor can silently mis-handle non-WAV references
    # (soundfile has no AAC/m4a decoder of its own) -- normalize once here so
    # every later clone call, preview, and comparison gets a format it can
    # actually read instead of falling back to un-cloned audio.
    ref_path = profile_dir / "reference.wav"
    if ext == ".wav":
        raw_path.rename(ref_path)
    else:
        subprocess.run(
            [FFMPEG_BIN, "-y", "-i", str(raw_path), "-ar", "48000", "-ac", "1", str(ref_path)],
            capture_output=True, timeout=60,
        )
        if ref_path.exists() and ref_path.stat().st_size > 100:
            raw_path.unlink(missing_ok=True)
        else:
            # conversion failed -- keep the original so the profile isn't silently empty
            raw_path.rename(profile_dir / f"reference{ext}")
            ref_path = profile_dir / f"reference{ext}"

    duration = _get_audio_duration(str(ref_path))

    meta = {
        "name": name,
        "original_filename": filename,
        "duration": round(duration, 1),
        "created_at": __import__("time").time(),
    }
    with open(profile_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    meta["id"] = voice_id
    return meta


def delete_voice_profile(voice_id: str) -> bool:
    profile_dir = VOICES_DIR / voice_id
    if profile_dir.exists() and profile_dir.is_dir():
        shutil.rmtree(str(profile_dir))
        return True
    return False


def _get_audio_duration(path: str) -> float:
    try:
        from scripts.utils import get_audio_duration
        return get_audio_duration(path)
    except Exception:
        return 0.0


FFMPEG_BIN = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")


def _child_env() -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PATH"] = os.path.dirname(FFMPEG_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _se_cache_dir(reference_audio_path: str) -> str:
    """Reference speaker embeddings are cached beside the voice profile, so
    a profile is analysed once instead of on every clone."""
    return os.path.join(os.path.dirname(reference_audio_path), "se_cache")


async def clone_voice(
    base_audio_path: str,
    reference_audio_path: str,
    output_path: str,
    tau: float = 0.3,
) -> bool:
    """Convert base_audio_path to the reference speaker's voice. Returns False
    (and writes nothing) if cloning failed, so the caller can fall back."""
    import asyncio
    return await asyncio.to_thread(
        _clone_voice_sync, base_audio_path, reference_audio_path, output_path, tau,
    )


def _clone_voice_sync(
    base_audio_path: str,
    reference_audio_path: str,
    output_path: str,
    tau: float = 0.3,
) -> bool:
    work_dir = os.path.join(os.path.dirname(os.path.abspath(output_path)), "se_tmp")
    script = f'''
import sys, os, shutil, subprocess
sys.path.insert(0, r"{BASE_DIR}")
import torch
dev = "cuda" if torch.cuda.is_available() else "cpu"
try:
    from openvoice.api import ToneColorConverter
    from openvoice import se_extractor

    ckpt_path = os.environ.get("OPENVOICE_CKPT", r"{BASE_DIR / "models" / "openvoice" / "checkpoints_v2"}")
    converter = ToneColorConverter(os.path.join(ckpt_path, "converter", "config.json"), device=dev)
    converter.watermark_model = None
    converter.load_ckpt(os.path.join(ckpt_path, "converter", "checkpoint.pth"))

    def get_se(path, target_dir):
        try:
            return se_extractor.get_se(path, converter, target_dir=target_dir, vad=True)[0]
        except AssertionError:
            return se_extractor.get_se(path, converter, target_dir=target_dir, vad=False)[0]

    source_se = get_se(r"{base_audio_path}", r"{work_dir}")
    target_se = get_se(r"{reference_audio_path}", r"{_se_cache_dir(reference_audio_path)}")

    raw_out = r"{output_path}".replace(".wav", "_22k.wav")
    converter.convert(audio_src_path=r"{base_audio_path}", src_se=source_se,
                      tgt_se=target_se, output_path=raw_out, tau={tau})
    subprocess.run([r"{FFMPEG_BIN}", "-y", "-i", raw_out, "-ar", "48000",
                    "-acodec", "pcm_s16le", r"{output_path}"], capture_output=True, timeout=120)
    os.remove(raw_out)
    if dev == "cuda":
        del converter
        torch.cuda.empty_cache()
    print("CLONE_OK" if os.path.getsize(r"{output_path}") > 100 else "CLONE_FAIL: empty output")
except Exception as e:
    print(f"CLONE_FAIL: {{e}}")
finally:
    shutil.rmtree(r"{work_dir}", ignore_errors=True)
'''
    try:
        audio_seconds = _get_audio_duration(base_audio_path)
    except Exception:
        audio_seconds = 60
    timeout = int(min(900, 120 + 3 * audio_seconds))
    try:
        result = subprocess.run(
            [VENV_PYTHON, "-c", script],
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(BASE_DIR), env=_child_env(),
        )
    except subprocess.TimeoutExpired:
        print(f"Voice cloning timed out after {timeout}s")
        return False
    if "CLONE_OK" in (result.stdout or "") and os.path.exists(output_path):
        return True
    print(f"Voice cloning failed: {((result.stdout or '') + (result.stderr or ''))[-400:]}")
    return False


_BATCH_SCRIPT = r'''
import sys, os, json, shutil, subprocess
sys.path.insert(0, r"{base_dir}")

import torch
from openvoice.api import ToneColorConverter
from openvoice import se_extractor

dev = "cuda" if torch.cuda.is_available() else "cpu"
ckpt_path = r"{ckpt_path}"

converter = ToneColorConverter(os.path.join(ckpt_path, "converter", "config.json"), device=dev)
converter.watermark_model = None
converter.load_ckpt(os.path.join(ckpt_path, "converter", "checkpoint.pth"))

def get_se(path, target_dir):
    try:
        return se_extractor.get_se(path, converter, target_dir=target_dir, vad=True)[0]
    except AssertionError:
        return se_extractor.get_se(path, converter, target_dir=target_dir, vad=False)[0]

base_audio_path = r"{base_audio_path}"
# Extracted once and reused for every voice below -- this is the whole point
# of batching: model load + source-tone extraction dominate the per-call
# cost, and both are identical across voices when the test text is fixed.
source_se = get_se(base_audio_path, os.path.join(os.path.dirname(base_audio_path), "se_tmp"))

jobs = json.loads(sys.stdin.read())  # [[voice_id, ref_path, out_path], ...]

for voice_id, ref_path, out_path in jobs:
    try:
        target_se = get_se(ref_path, os.path.join(os.path.dirname(ref_path), "se_cache"))
        converter.convert(
            audio_src_path=base_audio_path,
            src_se=source_se,
            tgt_se=target_se,
            output_path=out_path,
            tau={tau},
        )
        resampled = out_path + ".48k.wav"
        subprocess.run(
            [r"{ffmpeg_bin}", "-y", "-i", out_path, "-ar", "48000", "-acodec", "pcm_s16le", resampled],
            capture_output=True, timeout=60,
        )
        if os.path.exists(resampled) and os.path.getsize(resampled) > 100:
            shutil.move(resampled, out_path)
        print(f"VOICE_DONE:{{voice_id}}", flush=True)
    except Exception as e:
        print(f"VOICE_FAIL:{{voice_id}}:{{e}}", flush=True)

if dev == "cuda":
    del converter
    torch.cuda.empty_cache()
print("BATCH_DONE", flush=True)
'''


def start_clone_batch_process(
    base_audio_path: str,
    jobs: list[tuple[str, str, str]],
    tau: float = 0.3,
) -> subprocess.Popen:
    """Launch one subprocess that loads OpenVoice once and clones against every
    (voice_id, reference_path, output_path) triple in `jobs`. Prints
    "VOICE_DONE:{id}" / "VOICE_FAIL:{id}:{err}" per voice as it finishes, then
    "BATCH_DONE" -- read line-by-line from stdout for live progress.
    """
    script = _BATCH_SCRIPT.format(
        base_dir=str(BASE_DIR),
        ffmpeg_bin=FFMPEG_BIN,
        ckpt_path=str(BASE_DIR / "models" / "openvoice" / "checkpoints_v2"),
        base_audio_path=base_audio_path,
        tau=tau,
    )
    proc = subprocess.Popen(
        [VENV_PYTHON, "-c", script],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", errors="replace", cwd=str(BASE_DIR), bufsize=1,
        env=_child_env(),
    )
    proc.stdin.write(json.dumps(jobs))
    proc.stdin.close()
    return proc
