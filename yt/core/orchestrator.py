import glob
import json
import os
import shutil
import time
import uuid
import traceback
from dataclasses import dataclass
from core.logger import ProjectStatus
from scripts.generate_script import generate_script, DURATION_PRESETS
from scripts.generate_audio import generate_audio
from scripts.create_video import create_video
from scripts.fetch_images import fetch_background_media

# Phases where a background task is actually running; a server restart
# orphans these. media_ready waits on the user, so it survives restarts.
_IN_FLIGHT = {"pending", "brainstorming", "script_done", "generating_audio",
              "audio_done", "creating_video"}


@dataclass
class VoiceSettings:
    voice: str = "female"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    clone_voice_id: str = ""
    tone: str = "normal"
    tone_preset: dict | None = None
    clone_tau: float = 0.3
    clone_engine: str = "openvoice"


def _cleanup_intermediates(project_id: str):
    base = os.path.join("projects", project_id)
    for d in ("audio/segments", "audio/tone_clips", "audio/clips", "audio/se_tmp"):
        shutil.rmtree(os.path.join(base, d), ignore_errors=True)
    patterns = ("audio/base_tts*", "audio/final_mix*", "audio/mixed.*",
                "media/img_clip_*", "output/*.ass", "output/*_overlay.png")
    for pattern in patterns:
        for f in glob.glob(os.path.join(base, pattern)):
            try:
                os.remove(f)
            except OSError:
                pass


class Orchestrator:
    def __init__(self):
        self.projects: dict[str, ProjectStatus] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        projects_dir = "projects"
        if not os.path.isdir(projects_dir):
            return
        cleaned = 0
        for name in os.listdir(projects_dir):
            status_path = os.path.join(projects_dir, name, "status.json")
            if not os.path.isfile(status_path):
                continue
            try:
                with open(status_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError) as e:
                print(f"Skipping project {name}: unreadable status.json ({e})")
                continue
            status = ProjectStatus.from_dict(data)
            if status.phase in _IN_FLIGHT:
                status.update("error", 0, error="Pipeline interrupted (server restarted)")
                cleaned += 1
            self.projects[name] = status
        if cleaned:
            print(f"Marked {cleaned} interrupted project(s) as error")

    def create_project(self, topic: str) -> str:
        project_id = uuid.uuid4().hex[:8]
        self.projects[project_id] = ProjectStatus(project_id=project_id, topic=topic)
        return project_id

    def get_status(self, project_id: str) -> dict:
        status = self.projects.get(project_id)
        if not status:
            return {"error": "Project not found"}
        return status.to_dict()

    def list_projects(self) -> list[dict]:
        return [s.to_dict() for s in self.projects.values()]

    async def generate(self, project_id: str, topic: str, voice_settings: VoiceSettings | None = None,
                       skip_media_fetch: bool = False, subtitles: bool = True, persona: str = "",
                       custom_script: str = "", bgm_path: str = "", bgm_volume: float = 0.2,
                       aspect_ratios: list[str] | None = None, mode: str = "narration",
                       voice_b: str = "", overlay_opts: dict | None = None,
                       duration_preset: str = "short", media_durations: list[float] | None = None):
        vs = voice_settings or VoiceSettings()
        status = self.projects[project_id]
        try:
            clone_name = ""
            if vs.clone_voice_id:
                from scripts.voice_clone import list_voice_profiles
                for p in list_voice_profiles():
                    if p["id"] == vs.clone_voice_id:
                        clone_name = p.get("name", vs.clone_voice_id)
                        break
            status.voice_settings = {
                "voice": vs.voice, "rate": vs.rate, "pitch": vs.pitch,
                "tone": vs.tone,
                "clone_voice_id": vs.clone_voice_id,
                "clone_name": clone_name,
                "clone_engine": vs.clone_engine,
                "clone_tau": vs.clone_tau,
            }
            mode_label = "สนทนา 2 คน" if mode == "dialogue" else "บรรยาย"
            status.log(f"เริ่มสร้างคลิป ({mode_label}): {topic}")
            preset = DURATION_PRESETS.get(duration_preset, DURATION_PRESETS["short"])
            status.log(f"ความยาว: {preset['label_th']}")
            if custom_script.strip():
                status.log("ใช้สคริปต์กำหนดเอง — ข้ามระดมสมอง+สร้างสคริปต์")
            else:
                if persona.strip():
                    status.log(f"บุคลิกตัวละคร: {persona[:60]}")
                status.log("ระดมสมอง Gemini + เขียนสคริปต์ Ollama...")
            status.update("brainstorming", 10)
            script = await generate_script(project_id, topic, voice=vs.voice,
                                           persona=persona, custom_script=custom_script,
                                           mode=mode, duration_preset=duration_preset,
                                           log=status.log)
            status.log(f"ได้สคริปต์ {len(script)} ตัวอักษร", "success")
            status.update("script_done", 35, script=script)

            if vs.clone_voice_id:
                voice_desc = f"โคลนเสียง '{clone_name or vs.clone_voice_id[:8]}' ({vs.clone_engine})"
            else:
                voice_desc = f"edge-tts: {vs.voice}"
            if vs.tone != "normal":
                voice_desc += f" | โทน: {vs.tone}"
            status.log(f"สร้างเสียง ({voice_desc})...")
            status.update("generating_audio", 50)
            audio_path = await generate_audio(
                project_id, script,
                voice=vs.voice, rate=vs.rate, pitch=vs.pitch,
                clone_voice_id=vs.clone_voice_id,
                mode=mode, voice_b=voice_b, tone=vs.tone,
                tone_preset=vs.tone_preset,
                clone_tau=vs.clone_tau,
                clone_engine=vs.clone_engine,
                log=status.log,
            )
            status.log("ได้เสียงแล้ว", "success")
            status.update("audio_done", 70, audio_path=audio_path)

            if skip_media_fetch:
                media_dir = os.path.join("projects", project_id, "media")
                videos = sorted(glob.glob(os.path.join(media_dir, "*_clip*")))
                images = sorted(glob.glob(os.path.join(media_dir, "*_img*")))
                status.log(f"ใช้สื่อที่อัปโหลด: {len(videos)} วิดีโอ, {len(images)} รูป")
            else:
                status.log("ดึงสื่อประกอบจาก Pexels...")
                status.update("creating_video", 75)
                orientation = "landscape" if aspect_ratios == ["16:9"] else "portrait"
                media = await fetch_background_media(project_id, topic, count=preset["media_count"],
                                                     orientation=orientation)
                status.log(f"ได้สื่อ: {len(media.get('videos', []))} วิดีโอ, "
                           f"{len(media.get('images', []))} รูป", "success")

            status.render_params = {
                "subtitles": subtitles,
                "bgm_path": bgm_path,
                "bgm_volume": bgm_volume,
                "aspect_ratios": aspect_ratios or ["9:16"],
                "mode": mode,
                "overlay_opts": overlay_opts or {},
                "media_durations": media_durations,
            }
            status.update("media_ready", 80)
            status.log("จัดเรียง media ใน Storyboard แล้วกด 'สร้างวิดีโอ'")

        except Exception:
            error_msg = traceback.format_exc()[-500:]
            status.log(error_msg[:200], "error")
            status.update("error", 0, error=error_msg)

    async def render_video(self, project_id: str):
        status = self.projects[project_id]
        render_start = time.time()
        try:
            params = status.render_params or {}
            media_dir = os.path.join("projects", project_id, "media")
            videos = sorted(f for f in glob.glob(os.path.join(media_dir, "[0-9][0-9]_clip*")))
            images = sorted(glob.glob(os.path.join(media_dir, "[0-9][0-9]_img*")))

            bgm_path = params.get("bgm_path", "")
            bgm_volume = params.get("bgm_volume", 0.2)
            ratios = params.get("aspect_ratios", ["9:16"])
            if bgm_path:
                status.log(f"ผสมเสียงประกอบ (volume {int(bgm_volume * 100)}%)...")
            video_paths = {}
            for i, ratio in enumerate(ratios):
                label = f"{ratio} ({i + 1}/{len(ratios)})" if len(ratios) > 1 else ratio
                status.log(f"สร้างวิดีโอ {label}...")
                status.update("creating_video", 85 + (i * 10 // len(ratios)))
                video_paths[ratio] = await create_video(
                    project_id, status.audio_path or "", script=status.script or "",
                    background_videos=videos,
                    background_images=images,
                    subtitles=params.get("subtitles", True),
                    bgm_path=bgm_path, bgm_volume=bgm_volume,
                    aspect_ratio=ratio,
                    overlay_opts=params.get("overlay_opts", {}),
                    media_durations=params.get("media_durations"),
                    log=status.log,
                )

            _cleanup_intermediates(project_id)
            m, s = divmod(int(time.time() - render_start), 60)
            status.log(f"เสร็จสิ้น! เรนเดอร์ใช้เวลา {m}:{s:02d}", "success")
            first_path = next(iter(video_paths.values()))
            status.update("done", 100, video_path=first_path, video_paths=video_paths, error=None)

        except Exception:
            error_msg = traceback.format_exc()[-500:]
            status.log(error_msg[:200], "error")
            status.update("error", 0, error=error_msg)
