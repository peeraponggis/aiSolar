"""F5-TTS-THAI voice cloning, run out-of-process.

F5-TTS-THAI pins numpy<=1.26.4, which conflicts with OpenVoice's environment,
so it lives in its own .venv-f5 (Python 3.12) and is driven over subprocess
exactly like voice_clone.py drives OpenVoice.
"""
import asyncio
import json
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
F5_VENV_PYTHON = BASE_DIR / ".venv-f5" / "Scripts" / "python.exe"
FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")
MAX_REF_SECONDS = 8


def is_f5_available() -> bool:
    """Interpreter plus the installed package on disk.

    Checked on the filesystem rather than by importing: f5_tts pulls in torch,
    which costs seconds, and this runs on every /api/tts-engines request.
    """
    if not F5_VENV_PYTHON.exists():
        return False
    site_packages = F5_VENV_PYTHON.parent.parent / "Lib" / "site-packages"
    return (site_packages / "f5_tts").is_dir()


# The child is started with -I, which ignores PYTHONIOENCODING, so stdout is
# switched to UTF-8 explicitly for the Thai reference transcript.
_SCRIPT = r'''
import sys, warnings
warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")
try:
    import torch
    from f5_tts.api import F5TTS
    from cached_path import cached_path
    import soundfile as sf

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # The pip package only ships *_train.yaml configs, but their `model:`
    # section is identical to what F5TTS() reads, so F5TTS_Base_train
    # doubles as the inference config. Checkpoint/vocab must be pointed at
    # VIZINTZOR/F5-TTS-THAI explicitly or F5TTS() defaults to the English
    # SWivid/F5-TTS weights instead.
    tts = F5TTS(
        model="F5TTS_Base_train",
        ckpt_file=str(cached_path("hf://VIZINTZOR/F5-TTS-THAI/model_1000000.pt")),
        vocab_file=str(cached_path("hf://VIZINTZOR/F5-TTS-THAI/vocab.txt")),
        device=device,
    )
    ref_file, ref_text, gen_text, out_path = sys.argv[1:5]
    if not ref_text:
        ref_text = tts.transcribe(ref_file)
        print("F5_REF_TEXT:" + ref_text.replace("\n", " "), flush=True)
    wav, sr, _ = tts.infer(ref_file=ref_file, ref_text=ref_text, gen_text=gen_text)
    sf.write(out_path, wav, sr)
    if device == "cuda":
        del tts
        torch.cuda.empty_cache()
    print("F5_CLONE_OK")
except Exception:
    import traceback
    print("F5_CLONE_FAIL:")
    traceback.print_exc()
    sys.exit(1)
'''


def _profile_cache(reference_audio: str) -> tuple[str, str]:
    """Trimmed 8 s reference and its transcript, cached in the voice profile
    folder so F5 does not re-trim and re-transcribe on every call."""
    profile_dir = os.path.dirname(os.path.abspath(reference_audio))
    trimmed = os.path.join(profile_dir, "f5_ref.wav")
    if not os.path.exists(trimmed) or os.path.getmtime(trimmed) < os.path.getmtime(reference_audio):
        subprocess.run(
            [FFMPEG, "-y", "-i", reference_audio, "-t", str(MAX_REF_SECONDS),
             "-ar", "24000", "-ac", "1", trimmed],
            capture_output=True, timeout=60,
        )
        _save_ref_text(profile_dir, "")
    if not os.path.exists(trimmed) or os.path.getsize(trimmed) < 100:
        return reference_audio, ""
    return trimmed, _load_meta(profile_dir).get("f5_ref_text", "")


def _load_meta(profile_dir: str) -> dict:
    try:
        with open(os.path.join(profile_dir, "metadata.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_ref_text(profile_dir: str, ref_text: str):
    meta_path = os.path.join(profile_dir, "metadata.json")
    if not os.path.exists(meta_path):
        return
    meta = _load_meta(profile_dir)
    meta["f5_ref_text"] = ref_text
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _clone_sync(text: str, reference_audio: str, output_path: str) -> str:
    if not is_f5_available():
        raise RuntimeError(
            "F5-TTS-THAI not installed. Create .venv-f5 and run: "
            "pip install git+https://github.com/VYNCX/F5-TTS-THAI.git"
        )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ref, ref_text = _profile_cache(reference_audio)

    # f5_tts's own audio loading shells out to ffmpeg by name.
    env = os.environ.copy()
    env["PATH"] = os.path.dirname(FFMPEG) + os.pathsep + env.get("PATH", "")
    timeout = int(min(1800, 180 + 0.6 * len(text)))

    try:
        # -I keeps the project directory off sys.path in the child.
        result = subprocess.run(
            [str(F5_VENV_PYTHON), "-I", "-c", _SCRIPT, ref, ref_text, text, output_path],
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(BASE_DIR), env=env,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"F5-TTS-THAI timed out after {timeout}s")

    stdout = result.stdout or ""
    for line in stdout.splitlines():
        if line.startswith("F5_REF_TEXT:") and ref != reference_audio:
            _save_ref_text(os.path.dirname(ref), line[len("F5_REF_TEXT:"):].strip())

    if "F5_CLONE_OK" in stdout and os.path.exists(output_path) \
            and os.path.getsize(output_path) > 100:
        return output_path
    raise RuntimeError(f"F5-TTS-THAI failed: {(stdout + (result.stderr or ''))[-2000:]}")


async def clone_with_f5(text: str, reference_audio: str, output_path: str) -> str:
    return await asyncio.to_thread(_clone_sync, text, reference_audio, output_path)
