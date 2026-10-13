"""
TTS Engine abstraction layer.
Each engine auto-detects its own availability; unavailable engines are
listed in the UI with install instructions but cannot be selected.
"""
import os
import re
import asyncio
import subprocess
import wave
from abc import ABC, abstractmethod
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FFMPEG = os.getenv("FFMPEG_PATH", "F:/LocalAI/tools/ffmpeg/ffmpeg.exe")

_engines: dict[str, "TTSEngine"] = {}
_clone_engines: dict[str, "CloneEngine"] = {}


class TTSEngine(ABC):
    name: str = ""
    label: str = ""
    install_hint: str = ""

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_voices(self) -> list[dict]: ...

    @abstractmethod
    async def synthesize(
        self, text: str, voice_id: str, output_path: str,
        rate: str = "+0%", pitch: str = "+0Hz",
    ) -> None: ...


class CloneEngine(ABC):
    name: str = ""
    label: str = ""
    install_hint: str = ""

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    async def clone(
        self, text: str, reference_audio: str, output_path: str,
        language: str = "th",
    ) -> None: ...


def register_engine(engine: TTSEngine):
    _engines[engine.name] = engine


def register_clone_engine(engine: CloneEngine):
    _clone_engines[engine.name] = engine


def get_engine(name: str) -> TTSEngine | None:
    return _engines.get(name)


def get_clone_engine(name: str) -> CloneEngine | None:
    return _clone_engines.get(name)


def list_engines() -> list[dict]:
    result = []
    for e in _engines.values():
        avail = e.is_available()
        result.append({
            "name": e.name,
            "label": e.label,
            "available": avail,
            "install_hint": e.install_hint,
            "voices": e.get_voices() if avail else [],
        })
    return result


def list_clone_engines() -> list[dict]:
    result = []
    for e in _clone_engines.values():
        avail = e.is_available()
        result.append({
            "name": e.name,
            "label": e.label,
            "available": avail,
            "install_hint": e.install_hint,
        })
    return result


# ---------------------------------------------------------------------------
# 1) edge-tts  (default, online)
# ---------------------------------------------------------------------------
class EdgeTTSEngine(TTSEngine):
    name = "edge-tts"
    label = "edge-tts (Microsoft)"
    install_hint = "pip install edge-tts"

    _VOICES = [
        {"id": "female", "name": "หญิง (เปรมวดี)", "gender": "female",
         "voice_name": "th-TH-PremwadeeNeural"},
        {"id": "male", "name": "ชาย (นิวัตน์)", "gender": "male",
         "voice_name": "th-TH-NiwatNeural"},
    ]

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def get_voices(self) -> list[dict]:
        return self._VOICES

    def _resolve_voice(self, voice_id: str) -> str:
        for v in self._VOICES:
            if v["id"] == voice_id:
                return v["voice_name"]
        return "th-TH-PremwadeeNeural"

    async def synthesize(self, text, voice_id, output_path, rate="+0%", pitch="+0Hz"):
        import edge_tts

        voice_name = self._resolve_voice(voice_id)
        comm = edge_tts.Communicate(text, voice_name, rate=rate, pitch=pitch)
        await asyncio.wait_for(comm.save(output_path), timeout=30)
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            raise RuntimeError("edge-tts produced empty audio")


# ---------------------------------------------------------------------------
# 2) PyThaiTTS / VachanaTTS  (offline, VITS, CPU ok)
# ---------------------------------------------------------------------------
class PyThaiTTSEngine(TTSEngine):
    name = "pythaitts"
    label = "PyThaiTTS (VachanaTTS)"
    install_hint = "pip install pythaitts"

    _VOICES = [
        {"id": "th_f_1", "name": "หญิง 1", "gender": "female"},
        {"id": "th_f_2", "name": "หญิง 2", "gender": "female"},
        {"id": "th_m_1", "name": "ชาย 1", "gender": "male"},
        {"id": "th_m_2", "name": "ชาย 2", "gender": "male"},
    ]

    _tts_instance = None

    def is_available(self) -> bool:
        try:
            from pythaitts import TTS  # noqa: F401
            return True
        except Exception:
            return False

    def get_voices(self) -> list[dict]:
        return self._VOICES

    def _get_tts(self):
        if self._tts_instance is None:
            from pythaitts import TTS
            self._tts_instance = TTS(pretrained="vachana")
        return self._tts_instance

    async def synthesize(self, text, voice_id, output_path, rate="+0%", pitch="+0Hz"):
        tts = self._get_tts()
        wav_path = output_path if output_path.endswith(".wav") else output_path + ".wav"
        await asyncio.to_thread(
            tts.tts, text, speaker_idx=voice_id, filename=wav_path,
        )
        if wav_path != output_path:
            subprocess.run(
                [FFMPEG, "-y", "-i", wav_path, "-c:a", "libmp3lame", "-q:a", "2",
                 output_path],
                capture_output=True, timeout=30,
            )
            os.remove(wav_path)


# ---------------------------------------------------------------------------
# 3) Piper TTS  (offline, ONNX, fast)
# ---------------------------------------------------------------------------
class PiperTTSEngine(TTSEngine):
    name = "piper"
    label = "Piper TTS"
    install_hint = "pip install piper-tts  (ต้องดาวน์โหลด Thai voice model แยก)"

    _voice_cache: list[dict] | None = None

    def is_available(self) -> bool:
        try:
            from piper import PiperVoice  # noqa: F401
            return True
        except Exception:
            return False

    def _find_voice_models(self) -> list[dict]:
        """Scan for downloaded Thai .onnx voice models."""
        if self._voice_cache is not None:
            return self._voice_cache
        voices = []
        search_dirs = [
            BASE_DIR / "models" / "piper",
            Path.home() / ".local" / "share" / "piper_tts",
            Path(os.environ.get("PIPER_VOICES_DIR", "")),
        ]
        for d in search_dirs:
            if not d.is_dir():
                continue
            for onnx in d.rglob("*.onnx"):
                config = onnx.with_suffix(".onnx.json")
                if config.exists():
                    name = onnx.stem
                    voices.append({
                        "id": str(onnx),
                        "name": name,
                        "gender": "female" if "female" in name.lower() else "male",
                        "config": str(config),
                    })
        self._voice_cache = voices
        return voices

    def get_voices(self) -> list[dict]:
        return self._find_voice_models()

    async def synthesize(self, text, voice_id, output_path, rate="+0%", pitch="+0Hz"):
        from piper import PiperVoice

        config_path = None
        for v in self._find_voice_models():
            if v["id"] == voice_id:
                config_path = v.get("config")
                break

        voice = PiperVoice.load(voice_id, config_path=config_path)
        wav_path = output_path if output_path.endswith(".wav") else output_path + ".wav"

        def _do_synth():
            with wave.open(wav_path, "wb") as wf:
                voice.synthesize(text, wf)

        await asyncio.to_thread(_do_synth)

        if wav_path != output_path:
            subprocess.run(
                [FFMPEG, "-y", "-i", wav_path, "-c:a", "libmp3lame", "-q:a", "2",
                 output_path],
                capture_output=True, timeout=30,
            )
            os.remove(wav_path)


# ---------------------------------------------------------------------------
# 4) MOSS-TTS Nano  (offline, voice clone, GPU recommended)
# ---------------------------------------------------------------------------
class MossTTSEngine(TTSEngine):
    name = "moss-tts"
    label = "MOSS-TTS Nano"
    install_hint = (
        "git clone https://github.com/OpenMOSS/MOSS-TTS-Nano && "
        "cd MOSS-TTS-Nano && pip install -e ."
    )

    _VOICES = [
        {"id": "default", "name": "Default (reference clip)", "gender": "female"},
    ]

    def is_available(self) -> bool:
        try:
            from moss_tts_nano import MossTTSNano  # noqa: F401
            return True
        except Exception:
            return False

    def get_voices(self) -> list[dict]:
        ref_dir = BASE_DIR / "voices"
        voices = list(self._VOICES)
        if ref_dir.is_dir():
            for d in sorted(ref_dir.iterdir()):
                ref = d / "reference.wav"
                if not ref.exists():
                    for ext in (".mp3", ".m4a", ".ogg", ".flac"):
                        ref = d / f"reference{ext}"
                        if ref.exists():
                            break
                if ref.exists():
                    voices.append({
                        "id": f"voice:{d.name}",
                        "name": f"Clone: {d.name}",
                        "gender": "female",
                        "reference": str(ref),
                    })
        return voices

    async def synthesize(self, text, voice_id, output_path, rate="+0%", pitch="+0Hz"):
        from moss_tts_nano import MossTTSNano
        import soundfile as sf

        model = MossTTSNano.from_pretrained("OpenMOSS-Team/MOSS-TTS-Nano-100M")

        ref_path = None
        if voice_id.startswith("voice:"):
            vid = voice_id[6:]
            from scripts.voice_clone import get_reference_path
            ref_path = get_reference_path(vid)

        if not ref_path:
            ref_path = str(BASE_DIR / "models" / "moss-tts" / "default_ref.wav")
            if not os.path.exists(ref_path):
                raise RuntimeError(
                    "MOSS-TTS requires a reference audio clip. "
                    "Upload a voice profile or place default_ref.wav in models/moss-tts/"
                )

        wav_path = output_path if output_path.endswith(".wav") else output_path + ".wav"
        result = await asyncio.to_thread(
            model.synthesize, text, ref_path, language="th",
        )
        sf.write(wav_path, result["audio"], result.get("sample_rate", 48000))

        if wav_path != output_path:
            subprocess.run(
                [FFMPEG, "-y", "-i", wav_path, "-c:a", "libmp3lame", "-q:a", "2",
                 output_path],
                capture_output=True, timeout=60,
            )
            os.remove(wav_path)


# ---------------------------------------------------------------------------
# Clone Engine: F5-TTS-THAI
# ---------------------------------------------------------------------------
class F5TTSThaiCloneEngine(CloneEngine):
    name = "f5-tts-thai"
    label = "F5-TTS-THAI"
    install_hint = (
        "สร้าง .venv-f5 (Python 3.12) แล้ว "
        "pip install git+https://github.com/VYNCX/F5-TTS-THAI.git"
    )

    def is_available(self) -> bool:
        from scripts.f5_clone import is_f5_available
        return is_f5_available()

    async def clone(self, text, reference_audio, output_path, language="th"):
        """Generate speech in the style of the reference audio (1-step, no base TTS)."""
        from scripts.f5_clone import clone_with_f5
        await clone_with_f5(text, reference_audio, output_path)


# ---------------------------------------------------------------------------
# Clone Engine: OpenVoice V2  (existing system, wrapper)
# ---------------------------------------------------------------------------
class OpenVoiceCloneEngine(CloneEngine):
    name = "openvoice"
    label = "OpenVoice V2"
    install_hint = "ติดตั้งแล้วใน .venv-clone"

    def is_available(self) -> bool:
        venv_python = BASE_DIR / ".venv-clone" / "Scripts" / "python.exe"
        return venv_python.exists()

    async def clone(self, text, reference_audio, output_path, language="th"):
        from scripts.voice_clone import clone_voice
        await clone_voice(text, reference_audio, output_path)


# ---------------------------------------------------------------------------
# Register all engines on import
# ---------------------------------------------------------------------------
register_engine(EdgeTTSEngine())
register_engine(PyThaiTTSEngine())
register_engine(PiperTTSEngine())
register_engine(MossTTSEngine())

register_clone_engine(OpenVoiceCloneEngine())
register_clone_engine(F5TTSThaiCloneEngine())
