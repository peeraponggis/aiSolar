# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

import glob
import json
import os
import re
import shutil
import time
import uuid
import traceback
from dataclasses import dataclass
from core.logger import ProjectStatus
from scripts.generate_script import generate_script, generate_scene_script, DURATION_PRESETS
from scripts.generate_audio import generate_audio
from scripts.create_video import create_video, XFADE_DUR
from scripts.fetch_images import fetch_background_media, fetch_scene_media

# Phases where a background task is actually running; a server restart
# orphans these. media_ready waits on the user, so it survives restarts.
_IN_FLIGHT = {"pending", "brainstorming", "script_done", "generating_audio",
              "audio_done", "creating_video"}

RUN_MODES = {"semi": "กึ่งอัตโนมัติ", "review": "อัตโนมัติ + หยุดตรวจ", "auto": "อัตโนมัติเต็ม"}


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
                "media/img_clip_*", "output/*.ass", "output/*_overlay.png", "output/preview_*")
    for pattern in patterns:
        for f in glob.glob(os.path.join(base, pattern)):
            try:
                os.remove(f)
            except OSError:
                pass


def _letters(text: str) -> int:
    text = re.sub(r"^\s*[AB]\s*[:：]\s*", "", text, flags=re.M)
    return len(re.sub(r"\s+", "", text))


def scene_spans(scenes: list[dict], project_id: str, total: float) -> list[float]:
    """How long each scene is spoken, from audio/timings.json. Each timing block
    is assigned to the scene its text falls in (by cumulative letter count)."""
    path = os.path.join("projects", project_id, "audio", "timings.json")
    with open(path, encoding="utf-8") as f:
        timing = json.load(f)
    bounds, n = [], 0
    for s in scenes:
        n += _letters(s["text"])
        bounds.append(n)
    starts = [None] * len(scenes)
    done = 0
    for entry in timing:
        size = _letters(entry["text"])
        middle = done + size / 2
        done += size
        k = next((i for i, b in enumerate(bounds) if middle <= b), len(scenes) - 1)
        if starts[k] is None:
            starts[k] = float(entry["start"])
    starts[0] = 0.0
    for i in range(1, len(starts)):  # a scene with no timing block of its own
        if starts[i] is None:
            starts[i] = starts[i - 1]
    ends = starts[1:] + [total]
    return [max(0.5, e - s) for s, e in zip(starts, ends)]


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
                       duration_preset: str = "short", media_durations: list[float] | None = None,
                       run_mode: str = "semi", media_source: str = "pexels", ai_engine: str = "flux",
                       graphics: bool = False):
        vs = voice_settings or VoiceSettings()
        status = self.projects[project_id]
        status.run_mode = run_mode if run_mode in RUN_MODES else "semi"
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
            status.log(f"เริ่มสร้างคลิป ({mode_label} · โหมด{RUN_MODES[status.run_mode]}): {topic}")
            preset = DURATION_PRESETS.get(duration_preset, DURATION_PRESETS["short"])
            status.log(f"ความยาว: {preset['label_th']}")
            orientation = "landscape" if aspect_ratios == ["16:9"] else "portrait"
            render_params = {
                "subtitles": subtitles,
                "bgm_path": bgm_path,
                "bgm_volume": bgm_volume,
                "aspect_ratios": aspect_ratios or ["9:16"],
                "mode": mode,
                "overlay_opts": overlay_opts or {},
                "media_durations": media_durations,
            }

            if status.run_mode == "semi":
                await self._generate_classic(status, project_id, topic, vs, preset, persona,
                                             custom_script, mode, voice_b, duration_preset,
                                             skip_media_fetch, orientation, clone_name)
                status.render_params = render_params
                status.update("media_ready", 80)
                status.log("จัดเรียง media ใน Storyboard แล้วกด 'สร้างวิดีโอ'")
                return

            await self._generate_scenes(status, project_id, topic, vs, preset, persona,
                                        custom_script, mode, voice_b, duration_preset,
                                        skip_media_fetch, orientation, media_source, ai_engine,
                                        render_params, clone_name, graphics)

        except Exception:
            error_msg = traceback.format_exc()[-500:]
            status.log(error_msg[:200], "error")
            status.update("error", 0, error=error_msg)

    def _voice_desc(self, vs: VoiceSettings, clone_name: str) -> str:
        if vs.clone_voice_id:
            desc = f"โคลนเสียง '{clone_name or vs.clone_voice_id[:8]}' ({vs.clone_engine})"
        else:
            desc = f"edge-tts: {vs.voice}"
        return desc + (f" | โทน: {vs.tone}" if vs.tone != "normal" else "")

    async def _audio(self, status: ProjectStatus, project_id: str, script: str, vs: VoiceSettings,
                     mode: str, voice_b: str, clone_name: str, report: dict | None = None) -> str:
        status.log(f"สร้างเสียง ({self._voice_desc(vs, clone_name)})...")
        status.update("generating_audio", 50)
        audio_path = await generate_audio(
            project_id, script,
            voice=vs.voice, rate=vs.rate, pitch=vs.pitch,
            clone_voice_id=vs.clone_voice_id,
            mode=mode, voice_b=voice_b, tone=vs.tone,
            tone_preset=vs.tone_preset,
            clone_tau=vs.clone_tau,
            clone_engine=vs.clone_engine,
            log=status.log, report=report,
        )
        status.log("ได้เสียงแล้ว", "success")
        status.update("audio_done", 70, audio_path=audio_path)
        return audio_path

    async def _generate_classic(self, status, project_id, topic, vs, preset, persona, custom_script,
                                mode, voice_b, duration_preset, skip_media_fetch, orientation,
                                clone_name):
        """Semi-automatic mode: the original flow, unchanged."""
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
        await self._audio(status, project_id, script, vs, mode, voice_b, clone_name)
        if skip_media_fetch:
            media_dir = os.path.join("projects", project_id, "media")
            videos = sorted(glob.glob(os.path.join(media_dir, "*_clip*")))
            images = sorted(glob.glob(os.path.join(media_dir, "*_img*")))
            status.log(f"ใช้สื่อที่อัปโหลด: {len(videos)} วิดีโอ, {len(images)} รูป")
        else:
            status.log("ดึงสื่อประกอบจาก Pexels...")
            status.update("creating_video", 75)
            media = await fetch_background_media(project_id, topic, count=preset["media_count"],
                                                 orientation=orientation)
            status.log(f"ได้สื่อ: {len(media.get('videos', []))} วิดีโอ, "
                       f"{len(media.get('images', []))} รูป", "success")

    async def _generate_scenes(self, status, project_id, topic, vs, preset, persona, custom_script,
                               mode, voice_b, duration_preset, skip_media_fetch, orientation,
                               media_source, ai_engine, render_params, clone_name, graphics=False):
        """Review / auto modes: the script is a list of scenes, each with its own media."""
        from core.quality import check_before_render
        from scripts.utils import get_audio_duration

        media_dir = os.path.join("projects", project_id, "media")
        uploaded = sorted(f for f in glob.glob(os.path.join(media_dir, "[0-9][0-9]_*"))) \
            if skip_media_fetch else []
        status.log("เขียนสคริปต์แบบแบ่งฉาก (Gemini) + คำค้นภาพของแต่ละฉาก...")
        status.update("brainstorming", 10)
        res = await generate_scene_script(project_id, topic, voice=vs.voice, persona=persona,
                                          custom_script=custom_script, mode=mode,
                                          duration_preset=duration_preset,
                                          scene_count=len(uploaded) or None, log=status.log,
                                          want_stats=graphics and not uploaded)
        scenes = res["scenes"]
        status.scenes = scenes
        status.post = {"title": res["title"], "description": res["description"],
                       "hashtags": res["hashtags"]}
        status.log(f"ได้สคริปต์ {len(scenes)} ฉาก · ชื่อคลิป: {res['title']}", "success")
        status.update("script_done", 35, script=res["script"])

        report: dict = {}
        audio_path = await self._audio(status, project_id, res["script"], vs, mode, voice_b,
                                       clone_name, report)
        total = get_audio_duration(audio_path)
        spans = scene_spans(scenes, project_id, total)

        media = None
        if uploaded:
            status.log(f"ใช้สื่อที่อัปโหลด {len(uploaded)} ไฟล์ ตามลำดับฉาก")
        else:
            labels = {"pexels": "Pexels", "ai": "ภาพ AI", "mixed": "Pexels + ภาพ AI"}
            status.log(f"หาสื่อทีละฉาก ({labels.get(media_source, media_source)})...")
            status.update("creating_video", 75)
            media = await fetch_scene_media(project_id, scenes, topic, orientation=orientation,
                                            source=media_source, ai_engine=ai_engine,
                                            durations=spans, log=status.log, graphics=graphics)
            got = sum(1 for r in media if r["file"])
            status.log(f"ได้สื่อ {got}/{len(scenes)} ฉาก", "success" if got == len(scenes) else "warning")

        media_count = len(uploaded) or sum(1 for r in (media or []) if r["file"])
        if media_count == len(scenes):
            # Each picture stays up exactly while its scene is spoken; the
            # crossfade overlap is added back so cuts land on the scene change.
            render_params["media_durations"] = [d + XFADE_DUR if i < len(spans) - 1 else d
                                                for i, d in enumerate(spans)]
        status.render_params = render_params

        reasons = check_before_render(audio_path, preset, scenes, media, report,
                                      res.get("problems", []), bool(vs.clone_voice_id))
        status.review_reasons = reasons
        if status.run_mode == "auto" and not reasons:
            status.update("media_ready", 80)
            status.log("ผ่านด่านตรวจคุณภาพ — เรนเดอร์อัตโนมัติ", "success")
            await self.render_video(project_id)
            return
        status.update("media_ready", 80)
        if reasons:
            status.log("ต้องตรวจก่อนเรนเดอร์: " + "; ".join(reasons), "warning")
        else:
            status.log("พร้อมแล้ว — ตรวจ Storyboard / ดูตัวอย่างเร็ว แล้วกด 'สร้างวิดีโอ'")

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
            await self._finish(status, project_id, video_paths)
            m, s = divmod(int(time.time() - render_start), 60)
            status.log(f"เสร็จสิ้น! เรนเดอร์ใช้เวลา {m}:{s:02d}", "success")
            first_path = next(iter(video_paths.values()))
            status.update("done", 100, video_path=first_path, video_paths=video_paths, error=None)

        except Exception:
            error_msg = traceback.format_exc()[-500:]
            status.log(error_msg[:200], "error")
            status.update("error", 0, error=error_msg)

    async def _finish(self, status: ProjectStatus, project_id: str, video_paths: dict):
        """Post text, thumbnail, checks, and the automatic copy to F:\\LocalAI\\clips."""
        import asyncio
        from core.quality import check_after_render
        from scripts.post_assets import make_thumbnail, save_to_clips, write_post
        from scripts.utils import get_audio_duration

        output_dir = os.path.join("projects", project_id, "output")
        post = status.post or {"title": status.topic, "description": "", "hashtags": []}
        status.post = post
        try:
            problems = check_after_render(video_paths, get_audio_duration(status.audio_path))
            for p in problems:
                status.log(p, "warning")
            post_txt = write_post(output_dir, post)
            media = sorted(glob.glob(os.path.join("projects", project_id, "media", "[0-9][0-9]_*")))
            # A stat card already carries big text; the title reads better over footage.
            media = [m for m in media if "_card" not in os.path.basename(m)] or media
            ratio = next(iter(video_paths))
            size = (1080, 1920) if ratio == "9:16" else (1920, 1080)
            source = media[0] if media else next(iter(video_paths.values()))
            thumb = await asyncio.to_thread(make_thumbnail, source, post["title"],
                                            os.path.join(output_dir, "thumbnail.jpg"), size)
            folder = await asyncio.to_thread(save_to_clips, video_paths, [post_txt, thumb], post["title"])
            status.clips_folder = folder
            status.log(f"บันทึกไว้ที่ {folder}", "success")
        except Exception as e:
            status.log(f"สร้างข้อมูลโพสต์/บันทึกไป clips ไม่สำเร็จ: {e}", "warning")
