"""Voice-clone engines available on this machine (edge-tts is the only base TTS)."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def list_clone_engines() -> list[dict]:
    from scripts.f5_clone import is_f5_available
    return [
        {
            "name": "openvoice",
            "label": "OpenVoice V2",
            "available": (BASE_DIR / ".venv-clone" / "Scripts" / "python.exe").exists(),
            "install_hint": "สร้าง .venv-clone แล้วติดตั้ง OpenVoice V2",
        },
        {
            "name": "f5-tts-thai",
            "label": "F5-TTS-THAI",
            "available": is_f5_available(),
            "install_hint": (
                "สร้าง .venv-f5 (Python 3.12) แล้ว "
                "pip install git+https://github.com/VYNCX/F5-TTS-THAI.git"
            ),
        },
    ]
