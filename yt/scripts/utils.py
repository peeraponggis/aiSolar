import subprocess
import json
import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")


def _get_ffprobe() -> str:
    probe = os.path.join(os.path.dirname(FFMPEG), "ffprobe.exe")
    return probe if os.path.exists(probe) else "ffprobe"


def get_audio_duration(path: str) -> float:
    cmd = [
        _get_ffprobe(),
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return float(json.loads(result.stdout)["format"]["duration"])
    except (ValueError, KeyError, TypeError):
        raise RuntimeError(f"ffprobe could not read duration of {path}")
