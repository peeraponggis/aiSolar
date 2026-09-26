import subprocess
import json
import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")


def _get_ffprobe() -> str:
    ffmpeg = os.getenv("FFMPEG_PATH", FFMPEG)
    if ffmpeg and ffmpeg.endswith("ffmpeg.exe"):
        probe = ffmpeg[:-len("ffmpeg.exe")] + "ffprobe.exe"
        if os.path.exists(probe):
            return probe
    if ffmpeg and os.path.isfile(ffmpeg):
        parent = os.path.dirname(ffmpeg)
        probe = os.path.join(parent, "ffprobe.exe")
        if os.path.exists(probe):
            return probe
    return "ffprobe"


def get_audio_duration(path: str) -> float:
    cmd = [
        _get_ffprobe(),
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "json",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def sanitize_filename(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_ " else "" for c in name).strip()
