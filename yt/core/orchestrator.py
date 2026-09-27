import json
import os
import time
import uuid
import traceback
from dataclasses import dataclass
from core.logger import ProjectStatus
from scripts.generate_script import generate_script
from scripts.generate_audio import generate_audio
from scripts.create_video import create_video
from scripts.fetch_images import fetch_background_media


@dataclass
class VoiceSettings:
    voice: str = "female"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    clone_voice_id: str = ""
    tone: str = "normal"


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
            if os.path.isfile(status_path):
                try:
                    with open(status_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if data.get("phase") not in ("done", "error"):
                        data["phase"] = "error"
                        data["progress"] = 0
                        data["error"] = "Pipeline interrupted (server restarted)"
                        with open(status_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        cleaned += 1
                    self.projects[name] = ProjectStatus.from_dict(data)
                except Exception:
                    pass
        if cleaned:
            print(f"Cleaned up {cleaned} stuck project(s)")

    def create_project(self, topic: str) -> str:
        project_id = uuid.uuid4().hex[:8]
        self.projects[project_id] = ProjectStatus(
            project_id=project_id, topic=topic
        )
        return project_id

    def get_status(self, project_id: str) -> dict:
        status = self.projects.get(project_id)
        if not status:
            return {"error": "Project not found"}
        return status.to_dict()

    def list_projects(self) -> list[dict]:
        return [s.to_dict() for s in self.projects.values()]

    async def generate(self, project_id: str, topic: str, voice_settings: VoiceSettings | None = None, skip_media_fetch: bool = False, subtitles: bool = True, persona: str = "", custom_script: str = "", bgm_path: str = "", bgm_volume: float = 0.2, aspect_ratios: list[str] | None = None, mode: str = "narration", voice_b: str = "", overlay_opts: dict | None = None):
        vs = voice_settings or VoiceSettings()
        status = self.projects[project_id]
        try:
            mode_label = "สนทนา 2 คน" if mode == "dialogue" else "บรรยาย"
            status.log(f"เริ่มสร้างคลิป ({mode_label}): {topic}")
            if custom_script.strip():
                status.log("ใช้สคริปต์กำหนดเอง — ข้ามระดมสมอง+สร้างสคริปต์")
            elif persona.strip():
                status.log(f"บุคลิกตัวละคร: {persona[:60]}")

            if not custom_script.strip():
                status.log("ระดมสมอง Gemini 3.5 Flash...")
            status.update("brainstorming", 10)
            script = await generate_script(project_id, topic, voice=vs.voice,
                                           persona=persona, custom_script=custom_script,
                                           mode=mode)
            status.log(f"ได้สคริปต์ {len(script)} ตัวอักษร", "success")
            status.update("script_done", 35, script=script)

            if mode == "dialogue":
                vb = voice_b or ("male" if vs.voice == "female" else "female")
                name_a = "เปรมวดี" if vs.voice == "female" else "นิวัตน์"
                name_b = "เปรมวดี" if vb == "female" else "นิวัตน์"
                status.log(f"สร้างเสียงสนทนา A={name_a}, B={name_b}...")
            else:
                voice_name = "เปรมวดี" if vs.voice == "female" else "นิวัตน์"
                status.log(f"สร้างเสียง edge-tts ({voice_name})...")
            status.update("generating_audio", 50)
            audio_path = await generate_audio(
                project_id, script,
                voice=vs.voice, rate=vs.rate, pitch=vs.pitch,
                clone_voice_id=vs.clone_voice_id,
                mode=mode, voice_b=voice_b, tone=vs.tone,
            )
            if vs.clone_voice_id:
                status.log("ได้เสียง TTS — กำลังโคลนเสียง (OpenVoice V2)...")
                status.update("audio_done", 70, audio_path=audio_path,
                              extra_info="voice cloned")
            else:
                status.log("ได้เสียงแล้ว", "success")
                status.update("audio_done", 70, audio_path=audio_path)

            if skip_media_fetch:
                import glob
                media_dir = os.path.join("projects", project_id, "media")
                videos = sorted(glob.glob(os.path.join(media_dir, "*_clip*")))
                images = sorted(glob.glob(os.path.join(media_dir, "*_img*")))
                media = {"videos": videos, "images": images}
                status.log(f"ใช้สื่อที่อัปโหลด: {len(videos)} วิดีโอ, {len(images)} รูป")
                status.update("creating_video", 80)
            else:
                status.log("ดึงสื่อประกอบจาก Pexels...")
                status.update("creating_video", 75)
                media = await fetch_background_media(project_id, topic)
                status.log(f"ได้สื่อ: {len(media.get('videos',[]))} วิดีโอ, {len(media.get('images',[]))} รูป", "success")

            if bgm_path:
                status.log(f"ผสมเสียงประกอบ (volume {int(bgm_volume*100)}%)...")
            ratios = aspect_ratios or ["9:16"]
            video_paths = {}
            for i, ratio in enumerate(ratios):
                label = f"{ratio} ({i+1}/{len(ratios)})" if len(ratios) > 1 else ratio
                status.log(f"สร้างวิดีโอ FFmpeg {label}...")
                status.update("creating_video", 85 + (i * 10 // len(ratios)))
                vp = await create_video(
                    project_id, audio_path, script=script,
                    background_videos=media["videos"],
                    background_images=media["images"],
                    subtitles=subtitles,
                    bgm_path=bgm_path, bgm_volume=bgm_volume,
                    aspect_ratio=ratio,
                    mode=mode,
                    overlay_opts=overlay_opts or {},
                )
                video_paths[ratio] = vp

            elapsed = time.time() - status.created_at
            m, s = divmod(int(elapsed), 60)
            status.log(f"เสร็จสิ้น! ใช้เวลาทั้งหมด {m}:{s:02d}", "success")
            first_path = next(iter(video_paths.values()))
            status.update("done", 100, video_path=first_path, video_paths=video_paths)

        except Exception:
            error_msg = traceback.format_exc()[-500:]
            status.log(error_msg[:200], "error")
            status.update("error", 0, error=error_msg)
