import json
import os
import sys
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


def get_voice_profile(voice_id: str) -> dict | None:
    meta_path = VOICES_DIR / voice_id / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        meta["id"] = voice_id
        return meta
    except Exception:
        return None


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
    ref_path = profile_dir / f"reference{ext}"
    with open(ref_path, "wb") as f:
        f.write(audio_bytes)

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


async def clone_voice(
    base_audio_path: str,
    reference_audio_path: str,
    output_path: str,
    device: str = "auto",
) -> str:
    import asyncio
    return await asyncio.to_thread(
        _clone_voice_sync, base_audio_path, reference_audio_path, output_path, device
    )


def _clone_voice_sync(
    base_audio_path: str,
    reference_audio_path: str,
    output_path: str,
    device: str = "auto",
) -> str:
    script = f'''
import sys, os, shutil
sys.path.insert(0, r"{BASE_DIR}")
os.environ["PATH"] = r"F:\\LocalAI\\tools\\ffmpeg" + os.pathsep + os.environ.get("PATH", "")

import torch
if "{device}" == "auto":
    dev = "cuda" if torch.cuda.is_available() else "cpu"
else:
    dev = "{device}"

try:
    from openvoice.api import ToneColorConverter
    from openvoice import se_extractor

    ckpt_path = os.environ.get(
        "OPENVOICE_CKPT",
        r"{BASE_DIR / "models" / "openvoice" / "checkpoints_v2"}",
    )

    converter = ToneColorConverter(
        os.path.join(ckpt_path, "converter", "config.json"),
        device=dev,
    )
    converter.load_ckpt(os.path.join(ckpt_path, "converter", "checkpoint.pth"))

    source_se, _ = se_extractor.get_se(
        r"{base_audio_path}", converter, vad=False
    )
    try:
        target_se, _ = se_extractor.get_se(
            r"{reference_audio_path}", converter, vad=True
        )
    except AssertionError:
        target_se, _ = se_extractor.get_se(
            r"{reference_audio_path}", converter, vad=False
        )

    converter.convert(
        audio_src_path=r"{base_audio_path}",
        src_se=source_se,
        tgt_se=target_se,
        output_path=r"{output_path}",
    )

    if dev == "cuda":
        del converter
        torch.cuda.empty_cache()

    print("CLONE_OK")
except Exception as e:
    print(f"CLONE_FAIL: {{e}}")
    shutil.copy2(r"{base_audio_path}", r"{output_path}")
    print("FALLBACK_OK")
'''
    try:
        result = subprocess.run(
            [VENV_PYTHON, "-c", script],
            capture_output=True, text=True, timeout=120,
            cwd=str(BASE_DIR),
        )
        output = result.stdout + result.stderr
        if "CLONE_OK" in result.stdout:
            print("Voice cloning succeeded (subprocess)")
        elif "FALLBACK_OK" in result.stdout:
            print(f"Voice cloning fell back to original: {output[:200]}")
        else:
            print(f"Voice cloning subprocess error: {output[:300]}")
            shutil.copy2(base_audio_path, output_path)
    except Exception as e:
        print(f"Voice cloning subprocess failed: {e}")
        shutil.copy2(base_audio_path, output_path)

    return output_path
