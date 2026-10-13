"""F5-TTS-THAI voice cloning, run out-of-process.

F5-TTS-THAI pins numpy<=1.26.4, which conflicts with OpenVoice's environment,
so it lives in its own .venv-f5 (Python 3.12) and is driven over subprocess
exactly like voice_clone.py drives OpenVoice.
"""
import asyncio
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
F5_VENV_PYTHON = BASE_DIR / ".venv-f5" / "Scripts" / "python.exe"

def is_f5_available() -> bool:
    """Interpreter plus the installed package on disk.

    Checked on the filesystem rather than by importing: f5_tts pulls in torch,
    which costs seconds, and this runs on every /api/tts-engines request.
    """
    if not F5_VENV_PYTHON.exists():
        return False
    site_packages = F5_VENV_PYTHON.parent.parent / "Lib" / "site-packages"
    return (site_packages / "f5_tts").is_dir()


_SCRIPT = r'''
import sys, warnings
warnings.filterwarnings("ignore")
try:
    import torch
    from f5_tts.api import F5TTS
    import soundfile as sf

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tts = F5TTS(device=device)
    wav, sr, _ = tts.infer(
        ref_file=sys.argv[1],
        ref_text=sys.argv[2],
        gen_text=sys.argv[3],
    )
    sf.write(sys.argv[4], wav, sr)
    if device == "cuda":
        del tts
        torch.cuda.empty_cache()
    print("F5_CLONE_OK")
except Exception as e:
    print(f"F5_CLONE_FAIL: {e}")
    sys.exit(1)
'''


MAX_REF_SECONDS = 8
FFMPEG = str(BASE_DIR / "tools" / "ffmpeg" / "ffmpeg.exe")


def _trim_reference(reference_audio: str, work_dir: str) -> str:
    """F5 expects a 2-8s reference; saved profiles run much longer than that."""
    ffmpeg = FFMPEG if os.path.exists(FFMPEG) else "ffmpeg"
    trimmed = os.path.join(work_dir, "f5_ref_trimmed.wav")
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", reference_audio, "-t", str(MAX_REF_SECONDS),
             "-ar", "24000", "-ac", "1", trimmed],
            capture_output=True, timeout=60,
        )
        if os.path.exists(trimmed) and os.path.getsize(trimmed) > 100:
            return trimmed
    except Exception as e:
        print(f"Reference trim failed ({e}), using original")
    return reference_audio


def _clone_sync(text: str, reference_audio: str, output_path: str,
                ref_text: str = "") -> str:
    if not is_f5_available():
        raise RuntimeError(
            "F5-TTS-THAI not installed. Create .venv-f5 and run: "
            "pip install git+https://github.com/VYNCX/F5-TTS-THAI.git"
        )

    out_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(out_dir, exist_ok=True)
    ref = _trim_reference(reference_audio, out_dir)
    try:
        # -I keeps the project directory off sys.path in the child.
        result = subprocess.run(
            [str(F5_VENV_PYTHON), "-I", "-c", _SCRIPT,
             ref, ref_text, text, output_path],
            capture_output=True, text=True, timeout=600, cwd=str(BASE_DIR),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("F5-TTS-THAI timed out after 600s")

    if "F5_CLONE_OK" in result.stdout and os.path.exists(output_path) \
            and os.path.getsize(output_path) > 100:
        return output_path

    raise RuntimeError(f"F5-TTS-THAI failed: {(result.stdout + result.stderr)[-300:]}")


async def clone_with_f5(text: str, reference_audio: str, output_path: str,
                        ref_text: str = "") -> str:
    return await asyncio.to_thread(
        _clone_sync, text, reference_audio, output_path, ref_text
    )
