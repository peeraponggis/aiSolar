# ============================================================================
# ProInventive Suite
# Copyright (C) 2024-2569 ProInventive. All rights reserved.
#
# PROPRIETARY AND CONFIDENTIAL
# Unauthorized use, copying, or distribution is prohibited.
# Author: Peerapong (Lungpee) -- ProInventive -- giskku@gmail.com
# ============================================================================

import asyncio
import json
import os
import re
import shutil
import time
import uuid as _uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

from core.clip_queue import ClipQueue
from core.orchestrator import Orchestrator, VoiceSettings

BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"

_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}

app = FastAPI(title="YT Shorts Automation")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

orchestrator = Orchestrator()

# Event-loop tasks are only weakly referenced; keep them alive until done.
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return task


def _purge_old_files(directory: Path, max_age_s: float):
    if not directory.exists():
        return
    cutoff = time.time() - max_age_s
    for entry in directory.iterdir():
        try:
            if entry.stat().st_mtime < cutoff:
                if entry.is_dir():
                    shutil.rmtree(entry, ignore_errors=True)
                else:
                    entry.unlink()
        except OSError:
            pass


_purge_old_files(UPLOAD_DIR / "previews", 24 * 3600)
_purge_old_files(UPLOAD_DIR / "compare", 24 * 3600)


def _safe_name(value: str) -> bool:
    return bool(value) and not any(c in value for c in ("/", "\\", ".."))


@app.get("/")
async def root():
    return FileResponse(str(BASE_DIR / "static" / "dashboard.html"))


class GenerateRequest(BaseModel):
    """Sent as a JSON body: a long script in the URL hits the server's ~64 KB
    request-line limit (about 7,000 Thai characters)."""
    topic: str = Field(..., min_length=1)
    voice: str = "female"
    rate: str = "+0%"
    pitch: str = "+0Hz"
    media_files: str = ""
    subtitles: str = "on"
    clone_voice_id: str = ""
    persona: str = ""
    custom_script: str = ""
    bgm_file: str = ""
    bgm_volume: int = 20
    aspect_ratio: str = "9:16"
    mode: str = "narration"
    voice_b: str = ""
    tone: str = "normal"
    tone_var: int = 0
    tone_rate: int = 0
    tone_pitch: int = 0
    overlay_text: str = ""
    overlay_font: str = "sarabun"
    overlay_animation: str = "static"
    duration_preset: str = "short"
    clone_tau: int = 30
    media_durations: str = ""
    clone_engine: str = "openvoice"
    template_fields: str = ""
    run_mode: str = "semi"
    media_source: str = "pexels"
    ai_engine: str = "flux"
    graphics: str = "off"


def _prepare_generation(req: GenerateRequest):
    """Create the project and copy its inputs; returns (project_id, coroutine that runs it)."""
    topic, voice, rate, pitch = req.topic, req.voice, req.rate, req.pitch
    media_files, subtitles, clone_voice_id = req.media_files, req.subtitles, req.clone_voice_id
    persona, custom_script = req.persona, req.custom_script
    bgm_file, bgm_volume, aspect_ratio = req.bgm_file, req.bgm_volume, req.aspect_ratio
    mode, voice_b, tone = req.mode, req.voice_b, req.tone
    tone_var, tone_rate, tone_pitch = req.tone_var, req.tone_rate, req.tone_pitch
    overlay_text, overlay_font = req.overlay_text, req.overlay_font
    overlay_animation, duration_preset = req.overlay_animation, req.duration_preset
    clone_tau, media_durations = req.clone_tau, req.media_durations
    clone_engine, template_fields = req.clone_engine, req.template_fields

    project_id = orchestrator.create_project(topic)
    skip_fetch = False
    bgm_path = ""
    if bgm_file:
        src = UPLOAD_DIR / bgm_file
        if src.exists():
            audio_dir = BASE_DIR / "projects" / project_id / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            dest = audio_dir / f"bgm{src.suffix}"
            shutil.copy2(str(src), str(dest))
            bgm_path = str(dest)
    if media_files:
        file_list = [f.strip() for f in media_files.split(",") if f.strip()]
        if file_list:
            media_dir = BASE_DIR / "projects" / project_id / "media"
            media_dir.mkdir(parents=True, exist_ok=True)
            copied = 0
            for idx, fname in enumerate(file_list):
                src = UPLOAD_DIR / fname
                if not src.exists():
                    continue
                ext = src.suffix.lower()
                if ext in (".mp4", ".mov", ".avi", ".webm", ".gif"):
                    dest = media_dir / f"{idx:02d}_clip{ext}"
                else:
                    dest = media_dir / f"{idx:02d}_img{ext}"
                shutil.copy2(str(src), str(dest))
                copied += 1
            skip_fetch = copied > 0
    valid_tones = {"normal", "cheerful", "serious", "energetic", "warm", "news", "custom"}
    tone_val = tone if tone in valid_tones else "normal"
    tone_preset = None
    if tone_val == "custom":
        tone_preset = {
            "base_rate": max(-30, min(30, tone_rate)),
            "base_pitch": max(-30, min(30, tone_pitch)),
            "variation": max(0, min(30, tone_var)),
        }
    valid_presets = {"short", "medium", "long"}
    dur_preset = duration_preset if duration_preset in valid_presets else "short"
    tau_val = max(10, min(80, clone_tau)) / 100.0
    valid_clone = {"openvoice", "f5-tts-thai"}
    cleng = clone_engine if clone_engine in valid_clone else "openvoice"
    vs = VoiceSettings(voice=voice, rate=rate, pitch=pitch, clone_voice_id=clone_voice_id,
                       tone=tone_val, tone_preset=tone_preset, clone_tau=tau_val,
                       clone_engine=cleng)
    if aspect_ratio == "both":
        ratios = ["9:16", "16:9"]
    elif aspect_ratio in ("9:16", "16:9"):
        ratios = [aspect_ratio]
    else:
        ratios = ["9:16"]
    gen_mode = mode if mode in ("narration", "dialogue") else "narration"
    overlay_opts = {}
    if overlay_text.strip():
        valid_fonts = {"sarabun", "kanit"}
        valid_anims = {"static", "fade", "slide_up"}
        overlay_opts = {
            "overlay_text": overlay_text.strip(),
            "overlay_font": overlay_font if overlay_font in valid_fonts else "sarabun",
            "overlay_animation": overlay_animation if overlay_animation in valid_anims else "static",
        }
    if template_fields.strip():
        try:
            parsed_fields = json.loads(template_fields)
            if isinstance(parsed_fields, dict):
                overlay_opts["template_id"] = "social_repost"
                overlay_opts["template_fields"] = parsed_fields
        except ValueError:
            print("Ignoring template_fields: not valid JSON")
    dur_list = None
    if media_durations:
        try:
            dur_list = [float(d) for d in media_durations.split(",") if d.strip()]
        except ValueError:
            dur_list = None
    return project_id, (
        orchestrator.generate(project_id, topic, vs,
                              skip_media_fetch=skip_fetch,
                              subtitles=(subtitles == "on"),
                              persona=persona,
                              custom_script=custom_script,
                              bgm_path=bgm_path,
                              bgm_volume=bgm_volume / 100.0,
                              aspect_ratios=ratios,
                              mode=gen_mode,
                              voice_b=voice_b,
                              overlay_opts=overlay_opts,
                              duration_preset=dur_preset,
                              media_durations=dur_list,
                              run_mode=req.run_mode if req.run_mode in ("semi", "review", "auto") else "semi",
                              media_source=req.media_source if req.media_source in ("pexels", "ai", "mixed") else "pexels",
                              ai_engine=req.ai_engine if req.ai_engine in ("flux", "flux-fast", "gemini") else "flux",
                              graphics=req.graphics == "on")
    )


@app.post("/api/generate")
async def generate_video(req: GenerateRequest):
    project_id, job = _prepare_generation(req)
    _spawn(job)
    return {"id": project_id, "status": "processing"}


# ── Queue: many topics, one clip at a time, fully automatic ──

async def _run_queue_item(item: dict) -> str:
    req = GenerateRequest(**{**item["settings"], "run_mode": "auto"})
    project_id, job = _prepare_generation(req)
    item["project_id"] = project_id
    await job
    return project_id


clip_queue = ClipQueue(BASE_DIR / "queue" / "queue.json", _run_queue_item, orchestrator.projects)


@app.on_event("startup")
async def _start_queue_worker():
    _spawn(clip_queue.worker())


@app.get("/api/queue")
async def queue_list():
    return clip_queue.snapshot()


@app.post("/api/queue")
async def queue_add(request: Request):
    """{"settings": <GenerateRequest without topic>, "topics": ["...", ...]}"""
    body = await request.json()
    topics = [t.strip() for t in body.get("topics", []) if isinstance(t, str) and t.strip()]
    if not topics:
        return JSONResponse({"error": "ใส่หัวข้ออย่างน้อย 1 หัวข้อ"}, status_code=400)
    base = {k: v for k, v in (body.get("settings") or {}).items() if k in GenerateRequest.model_fields}
    # Each topic gets its own script and media.
    for own in ("custom_script", "media_files", "media_durations"):
        base.pop(own, None)
    added = []
    for topic in topics[:50]:
        settings = GenerateRequest(**{**base, "topic": topic, "run_mode": "auto"}).model_dump()
        added.append(clip_queue.add(settings)["id"])
    return {"added": len(added)}


@app.delete("/api/queue/{item_id}")
async def queue_remove(item_id: str):
    return {"ok": clip_queue.remove(item_id)}


@app.post("/api/queue/{item_id}/retry")
async def queue_retry(item_id: str):
    return {"ok": clip_queue.retry(item_id)}


@app.post("/api/queue/control")
async def queue_control(request: Request):
    action = (await request.json()).get("action")
    if action in ("pause", "resume"):
        clip_queue.set_paused(action == "pause")
    elif action == "clear_finished":
        clip_queue.clear_finished()
    return clip_queue.snapshot()


@app.get("/api/status/{project_id}")
async def get_status(project_id: str):
    return orchestrator.get_status(project_id)


@app.get("/api/logs/{project_id}")
async def get_logs(project_id: str, after: float = Query(0)):
    status = orchestrator.projects.get(project_id)
    if not status:
        return []
    return [e for e in status.logs if e["t"] > after]


@app.get("/api/projects")
async def list_projects():
    return orchestrator.list_projects()


@app.get("/api/project/{project_id}/media")
async def list_project_media(project_id: str):
    media_dir = BASE_DIR / "projects" / project_id / "media"
    if not media_dir.exists():
        return []
    files = sorted(media_dir.iterdir())
    result = []
    for f in files:
        if f.name.startswith("img_clip_"):
            continue
        ext = f.suffix.lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"):
            ftype = "image"
        elif ext in (".mp4", ".mov", ".avi", ".webm"):
            ftype = "video"
        else:
            continue
        result.append({"filename": f.name, "type": ftype})
    return result


@app.get("/api/project/{project_id}/media/{filename}")
async def serve_project_media(project_id: str, filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    path = BASE_DIR / "projects" / project_id / "media" / filename
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    ext = path.suffix.lower()
    types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
             ".webp": "image/webp", ".avif": "image/avif", ".gif": "image/gif",
             ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
    return FileResponse(str(path), media_type=types.get(ext, "application/octet-stream"))


VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv"}


def _apply_media_order(project_id: str, order: list[str]):
    """Renumber media to NN_clip.ext / NN_img.ext — the form render_video globs for.
    `order` is the storyboard's media, in order. Files the user removed from
    the storyboard are moved to media/_removed/ (not rendered, not deleted)."""
    media_dir = BASE_DIR / "projects" / project_id / "media"
    present = sorted(f.name for f in media_dir.iterdir()
                     if f.is_file() and re.match(r"\d+_(clip|img)", f.name))
    removed_dir = media_dir / "_removed"
    for name in present:
        if name not in order:
            removed_dir.mkdir(exist_ok=True)
            os.replace(media_dir / name, removed_dir / f"{_uuid.uuid4().hex[:6]}_{name}")
    ordered = [f for f in order if f in present]
    staged = []
    for i, fname in enumerate(ordered):
        src = media_dir / fname
        tmp = media_dir / f"__reorder_{i:03d}{src.suffix}"
        os.replace(src, tmp)
        kind = "clip" if src.suffix.lower() in VIDEO_EXTS else "img"
        if "_card" in fname:
            kind = "clip_card"  # keeps stat cards recognisable (e.g. skipped for the thumbnail)
        staged.append((tmp, media_dir / f"{i:02d}_{kind}{src.suffix}"))
    for tmp, final in staged:
        os.replace(tmp, final)


@app.post("/api/project/{project_id}/render")
async def render_project_video(project_id: str, request: Request):
    if project_id not in orchestrator.projects:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    status = orchestrator.projects[project_id]
    # A failed render can be retried: media/audio are already prepared.
    retryable = status.phase == "error" and status.render_params and status.audio_path
    if status.phase != "media_ready" and not retryable:
        return JSONResponse({"error": "Not ready"}, status_code=400)

    try:
        body = await request.json()
    except ValueError:
        body = {}

    if body.get("script"):
        status.script = body["script"]
    if isinstance(body.get("media_order"), list):
        _apply_media_order(project_id, body["media_order"])
    # Typed durations win; otherwise keep the automatic per-scene timing.
    if any(d and d > 0 for d in (body.get("media_durations") or [])) and status.render_params:
        status.render_params["media_durations"] = body["media_durations"]

    status.update("creating_video", 82, error=None)
    _spawn(orchestrator.render_video(project_id))
    return {"ok": True}


# ── Quick storyboard preview (half size, fast encode, nothing on disk renamed) ──

_preview_jobs: dict[str, dict] = {}


async def _run_preview(project_id: str, script: str, ordered: list[tuple[str, str]],
                       durations: list[float] | None, params: dict, ratio: str):
    from scripts.create_video import create_video
    job = _preview_jobs[project_id]
    status = orchestrator.projects[project_id]
    try:
        await create_video(
            project_id, status.audio_path or "", script=script,
            subtitles=params.get("subtitles", True),
            bgm_path=params.get("bgm_path", ""), bgm_volume=params.get("bgm_volume", 0.2),
            aspect_ratio=ratio, overlay_opts=params.get("overlay_opts", {}),
            media_durations=durations, preview=True, ordered=ordered,
        )
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)[-300:]
    job["seconds"] = round(time.time() - job["started"], 1)


@app.post("/api/project/{project_id}/preview")
async def start_preview(project_id: str, request: Request):
    status = orchestrator.projects.get(project_id)
    if not status:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    if not status.audio_path or not status.render_params:
        return JSONResponse({"error": "โปรเจคนี้ยังไม่พร้อมทำตัวอย่าง"}, status_code=400)
    if _preview_jobs.get(project_id, {}).get("status") == "running":
        return {"ok": True}
    try:
        body = await request.json()
    except ValueError:
        body = {}

    media_dir = BASE_DIR / "projects" / project_id / "media"
    order = body.get("media_order")
    if not isinstance(order, list):
        order = sorted(f.name for f in media_dir.iterdir()
                       if f.is_file() and re.match(r"\d+_(clip|img)", f.name))
    ordered = []
    for name in order:
        if _safe_name(name) and (media_dir / name).is_file():
            kind = "video" if Path(name).suffix.lower() in VIDEO_EXTS else "image"
            ordered.append((os.path.join("projects", project_id, "media", name), kind))

    params = status.render_params
    ratio = (params.get("aspect_ratios") or ["9:16"])[0]
    _preview_jobs[project_id] = {"status": "running", "error": None, "started": time.time(), "ratio": ratio}
    _spawn(_run_preview(project_id, body.get("script") or status.script or "", ordered,
                        body.get("media_durations") or params.get("media_durations"), params, ratio))
    return {"ok": True}


@app.get("/api/project/{project_id}/preview/status")
async def preview_status(project_id: str):
    job = _preview_jobs.get(project_id)
    if not job:
        return {"status": "none"}
    return {k: job.get(k) for k in ("status", "error", "seconds", "ratio")}


@app.get("/api/project/{project_id}/preview/video")
async def preview_video(project_id: str):
    job = _preview_jobs.get(project_id) or {}
    if not _safe_name(project_id) or job.get("status") != "done":
        return JSONResponse({"error": "Not ready"}, status_code=404)
    tag = job["ratio"].replace(":", "x")
    path = BASE_DIR / "projects" / project_id / "output" / f"preview_{tag}.mp4"
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(str(path), media_type="video/mp4", headers={"Cache-Control": "no-store"})


# ── Scenes, AI images, post text ──

@app.get("/api/project/{project_id}/scenes")
async def project_scenes(project_id: str):
    path = BASE_DIR / "projects" / project_id / "media" / "scenes.json"
    if not _safe_name(project_id) or not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/ai-image/status")
async def ai_image_status():
    from scripts.ai_images import ENGINE_LABELS, is_available
    return {"available": is_available(), "engines": ENGINE_LABELS}


@app.post("/api/project/{project_id}/ai-image")
async def project_ai_image(project_id: str, request: Request):
    """Draw one AI image for a storyboard scene and add it to the project's media."""
    from scripts.ai_images import generate_images
    from scripts.generate_script import image_prompt

    status = orchestrator.projects.get(project_id)
    if not status:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    body = await request.json()
    prompt = (body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "ใส่คำอธิบายภาพก่อน"}, status_code=400)
    engine = body.get("engine") if body.get("engine") in ("flux", "flux-fast", "gemini") else "flux"
    ratio = ((status.render_params or {}).get("aspect_ratios") or ["9:16"])[0]
    shape = "landscape" if ratio == "16:9" else "portrait"
    try:
        paths = await generate_images([image_prompt(prompt)], engine, shape)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    if not paths or not paths[0]:
        return JSONResponse({"error": "สร้างภาพไม่สำเร็จ"}, status_code=500)
    media_dir = BASE_DIR / "projects" / project_id / "media"
    name = f"99_img_{_uuid.uuid4().hex[:6]}{Path(paths[0]).suffix}"
    shutil.copy2(paths[0], media_dir / name)
    return {"filename": name, "type": "image"}


@app.get("/api/graphics/status")
async def graphics_status():
    from scripts.graphic_cards import is_available
    return {"available": await asyncio.to_thread(is_available)}


@app.post("/api/project/{project_id}/graphic-card")
async def project_graphic_card(project_id: str, request: Request):
    """Render one stat card for a storyboard scene from numbers the user typed."""
    from scripts.graphic_cards import render_stat_card

    status = orchestrator.projects.get(project_id)
    if not status:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    body = await request.json()
    raw = str(body.get("value", "")).replace(",", "").strip()
    try:
        value = float(raw)
    except ValueError:
        return JSONResponse({"error": "ใส่ตัวเลขให้ถูกต้อง"}, status_code=400)
    stat = {"value": value, "decimals": min(len(raw.split(".")[1]), 2) if "." in raw else 0,
            **{k: str(body.get(k) or "").strip()[:70] for k in ("label", "unit", "badge", "caption")}}
    try:
        seconds = float(body.get("duration") or 0)
    except (TypeError, ValueError):
        seconds = 0
    if seconds <= 0:
        durs = (status.render_params or {}).get("media_durations") or []
        idx = int(body.get("index") or 0)
        seconds = durs[idx] if 0 <= idx < len(durs) and durs[idx] else 0
    if seconds <= 0:
        # No per-scene timing (semi mode splits evenly): an even share plus margin,
        # since a clip shorter than its slot would loop and replay the count-up.
        from scripts.utils import get_audio_duration
        media_dir = BASE_DIR / "projects" / project_id / "media"
        count = len(status.scenes or []) or len(list(media_dir.glob("[0-9][0-9]_*"))) or 1
        try:
            total = get_audio_duration(status.audio_path) if status.audio_path else 0
        except RuntimeError:
            total = 0
        seconds = min(60.0, total / count * 1.5) if total else 8
    ratio = ((status.render_params or {}).get("aspect_ratios") or ["9:16"])[0]
    name = f"99_clip_card_{_uuid.uuid4().hex[:6]}.mp4"
    out = BASE_DIR / "projects" / project_id / "media" / name
    if not await render_stat_card(stat, str(out), seconds,
                                  "landscape" if ratio == "16:9" else "portrait"):
        return JSONResponse({"error": "สร้างการ์ดไม่สำเร็จ (ดู logs/graphic_cards.log)"}, status_code=500)
    return {"filename": name, "type": "video", "duration": round(seconds + 1, 2)}


@app.get("/api/project/{project_id}/thumbnail")
async def project_thumbnail(project_id: str):
    path = BASE_DIR / "projects" / project_id / "output" / "thumbnail.jpg"
    if not _safe_name(project_id) or not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(str(path), media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/api/download/{project_id}")
async def download_video(project_id: str, ratio: str = Query("")):
    if not _safe_name(project_id):
        return JSONResponse({"error": "Invalid"}, status_code=400)
    outputs = _project_outputs(project_id)
    path = outputs.get(ratio) if ratio else next(iter(outputs.values()), None)
    if not path:
        return JSONResponse({"error": "Video not found"}, status_code=404)
    return FileResponse(str(path), media_type="video/mp4", filename=path.name)


@app.get("/api/version")
async def app_version():
    return json.loads((BASE_DIR / "VERSION.json").read_text(encoding="utf-8"))


@app.get("/gallery")
async def gallery_page():
    return FileResponse(str(BASE_DIR / "static" / "gallery.html"))


_duration_cache: dict[str, tuple[float, float]] = {}
_thumb_sem = asyncio.Semaphore(4)


def _project_outputs(project_id: str) -> dict[str, Path]:
    """Finished videos on disk, keyed by ratio ("9:16"/"16:9")."""
    out_dir = BASE_DIR / "projects" / project_id / "output"
    found = {}
    for tag, ratio in (("9x16", "9:16"), ("16x9", "16:9")):
        p = out_dir / f"final_{tag}.mp4"
        if p.exists():
            found[ratio] = p
    legacy = out_dir / "final.mp4"
    if not found and legacy.exists():
        found["9:16"] = legacy
    return found


def _cached_duration(path: Path) -> float:
    from scripts.utils import get_audio_duration
    mtime = path.stat().st_mtime
    hit = _duration_cache.get(str(path))
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        dur = get_audio_duration(str(path))
    except RuntimeError:
        dur = 0.0
    _duration_cache[str(path)] = (mtime, dur)
    return dur


def _gallery_items() -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor

    entries = []
    for pid, status in orchestrator.projects.items():
        if status.phase != "done":
            continue
        outputs = _project_outputs(pid)
        if outputs:
            entries.append((pid, status, outputs))
    first_videos = [next(iter(o.values())) for _, _, o in entries]
    with ThreadPoolExecutor(max_workers=8) as pool:
        durations = list(pool.map(_cached_duration, first_videos))

    items = []
    for (pid, status, outputs), dur in zip(entries, durations):
        vs = status.voice_settings or {}
        items.append({
            "project_id": pid,
            "topic": status.topic,
            "created_at": status.created_at,
            "updated_at": status.updated_at,
            "ratios": list(outputs),
            "duration": round(dur, 1),
            "size": sum(p.stat().st_size for p in outputs.values()),
            "voice": vs.get("clone_name") or vs.get("voice") or "",
        })
    items.sort(key=lambda i: i["created_at"] or 0, reverse=True)
    return items


@app.get("/api/gallery")
async def gallery_list():
    return await asyncio.to_thread(_gallery_items)


def _make_thumb(video: Path, thumb: Path):
    import subprocess
    from scripts.create_video import FFMPEG
    subprocess.run([FFMPEG, "-y", "-ss", "1", "-i", str(video), "-frames:v", "1",
                    "-vf", "scale=360:-2", "-q:v", "4", str(thumb)],
                   capture_output=True, timeout=60)


@app.get("/api/gallery/thumb/{project_id}")
async def gallery_thumb(project_id: str, ratio: str = Query("9:16")):
    if not _safe_name(project_id):
        return JSONResponse({"error": "Invalid"}, status_code=400)
    video = _project_outputs(project_id).get(ratio)
    if not video:
        return JSONResponse({"error": "Not found"}, status_code=404)
    thumb = video.with_name(f"thumb_{ratio.replace(':', 'x')}.jpg")
    if not thumb.exists() or thumb.stat().st_mtime < video.stat().st_mtime:
        async with _thumb_sem:
            await asyncio.to_thread(_make_thumb, video, thumb)
    if not thumb.exists():
        return JSONResponse({"error": "Thumbnail failed"}, status_code=500)
    return FileResponse(str(thumb), media_type="image/jpeg",
                        headers={"Cache-Control": "max-age=86400"})


@app.get("/api/audio/{project_id}")
async def download_audio(project_id: str):
    audio_dir = BASE_DIR / "projects" / project_id / "audio"
    for name in ("narration.wav", "narration.mp3"):
        path = audio_dir / name
        if path.exists():
            return FileResponse(str(path), media_type=_MEDIA_TYPES[path.suffix], filename=name)
    return JSONResponse({"error": "Audio not found"}, status_code=404)


# ── Upload endpoints ──


@app.post("/api/upload")
async def upload_media(files: list[UploadFile] = File(...)):
    UPLOAD_DIR.mkdir(exist_ok=True)
    saved = []
    for f in files:
        ext = Path(f.filename or "file").suffix.lower()
        if ext not in _MEDIA_TYPES:
            continue
        safe_name = f"{_uuid.uuid4().hex[:8]}{ext}"
        dest = UPLOAD_DIR / safe_name
        content = await f.read()
        if len(content) > 100 * 1024 * 1024:
            continue
        with open(dest, "wb") as out:
            out.write(content)
        if ext in (".mp4", ".mov", ".avi", ".webm"):
            ftype = "video"
        elif ext in (".mp3", ".wav", ".m4a", ".ogg", ".flac"):
            ftype = "audio"
        else:
            ftype = "image"
        saved.append({
            "filename": safe_name,
            "original": f.filename,
            "type": ftype,
            "size": len(content),
        })
    return saved


@app.get("/api/uploads/file/{filename}")
async def serve_upload(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    path = UPLOAD_DIR / filename
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(str(path), media_type=media_type)


@app.delete("/api/uploads/{filename}")
async def delete_upload(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    path = UPLOAD_DIR / filename
    if path.exists():
        path.unlink()
        return {"ok": True}
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.post("/api/uploads/clear")
async def clear_uploads():
    if UPLOAD_DIR.exists():
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                f.unlink()
    return {"ok": True}


# ── Trim endpoint ──


@app.post("/api/uploads/trim")
async def trim_video(
    filename: str = Query(...),
    start: float = Query(0),
    end: float = Query(0),
):
    if "/" in filename or "\\" in filename or ".." in filename:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    src = UPLOAD_DIR / filename
    if not src.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    duration = end - start
    if duration < 0.5:
        return JSONResponse({"error": "Duration too short"}, status_code=400)

    from scripts.create_video import FFMPEG
    import subprocess

    safe_name = f"trimmed_{_uuid.uuid4().hex[:8]}.mp4"
    out_path = str(UPLOAD_DIR / safe_name)
    cmd = [
        FFMPEG, "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{duration:.3f}",
        "-c", "copy",
        "-movflags", "+faststart",
        out_path,
    ]
    result = await asyncio.to_thread(
        subprocess.run, cmd, capture_output=True, timeout=120,
        encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        return JSONResponse({"error": "Trim failed"}, status_code=500)
    return {"filename": safe_name, "type": "video", "ok": True}


# ── Voice preview endpoint ──


def _to_wav_48k(src: str, dst: str):
    import subprocess
    from scripts.generate_audio import FFMPEG
    subprocess.run([FFMPEG, "-y", "-i", src, "-c:a", "pcm_s16le", "-ar", "48000", dst],
                   capture_output=True, timeout=60)


def _send_and_delete(path: str, *cleanup: str) -> FileResponse:
    from starlette.background import BackgroundTask

    def remove_all():
        for p in (path, *cleanup):
            try:
                os.remove(p)
            except OSError:
                pass
    media = _MEDIA_TYPES.get(Path(path).suffix, "application/octet-stream")
    return FileResponse(path, media_type=media, filename="preview" + Path(path).suffix,
                        background=BackgroundTask(remove_all))


@app.post("/api/preview-voice")
async def preview_voice_tts(
    text: str = Query(..., min_length=1),
    voice: str = Query("female"),
    rate: str = Query("+0%"),
    pitch: str = Query("+0Hz"),
    tone: str = Query("normal"),
    tone_rate: int = Query(0),
    tone_pitch: int = Query(0),
    clone_voice_id: str = Query(""),
    clone_tau: int = Query(30),
    clone_engine: str = Query("openvoice"),
):
    from scripts.generate_audio import (
        VOICES, TONE_PRESETS, _clean_script_for_tts, _parse_signed, _fmt_rate, _fmt_pitch,
        _polish_audio, apply_replacements, load_replacements, _tts_with_retry,
    )

    processed = apply_replacements(_clean_script_for_tts(text), load_replacements())[:500]
    if tone == "custom":
        preset = {"base_rate": max(-30, min(30, tone_rate)),
                  "base_pitch": max(-30, min(30, tone_pitch))}
    else:
        preset = TONE_PRESETS.get(tone, TONE_PRESETS["normal"])
    # Same as generate_audio: the sliders are the base, the tone adds to it.
    rate = _fmt_rate(_parse_signed(rate) + preset["base_rate"])
    pitch = _fmt_pitch(_parse_signed(pitch) + preset["base_pitch"])

    preview_dir = UPLOAD_DIR / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    safe = str(preview_dir / f"preview_{_uuid.uuid4().hex[:8]}")

    if clone_voice_id and clone_engine == "f5-tts-thai":
        from scripts.voice_clone import get_reference_path
        from scripts.f5_clone import clone_with_f5, is_f5_available
        ref_path = get_reference_path(clone_voice_id)
        if ref_path and is_f5_available():
            try:
                await clone_with_f5(processed, ref_path, f"{safe}_f5.wav")
                await asyncio.to_thread(_polish_audio, f"{safe}_f5.wav")
                return _send_and_delete(f"{safe}_f5.wav")
            except RuntimeError as e:
                print(f"F5 clone preview failed, using OpenVoice: {str(e)[-300:]}")

    mp3 = f"{safe}.mp3"
    await _tts_with_retry(processed, VOICES.get(voice, VOICES["female"]), mp3, rate, pitch)

    if clone_voice_id:
        from scripts.voice_clone import clone_voice, get_reference_path
        ref_path = get_reference_path(clone_voice_id)
        if ref_path:
            base = f"{safe}_base.wav"
            await asyncio.to_thread(_to_wav_48k, mp3, base)
            cloned = f"{safe}_cloned.wav"
            tau = max(10, min(80, clone_tau)) / 100.0
            if await clone_voice(base, ref_path, cloned, tau=tau):
                await asyncio.to_thread(_polish_audio, cloned)
                return _send_and_delete(cloned, mp3, base)
            os.remove(base)

    return _send_and_delete(mp3)


# ── Voice presets (a tested combination of base voice + clone settings) ──

VOICE_PRESETS_PATH = BASE_DIR / "config" / "voice_presets.json"


def _load_voice_presets() -> list[dict]:
    if not VOICE_PRESETS_PATH.exists():
        return []
    return json.loads(VOICE_PRESETS_PATH.read_text(encoding="utf-8"))


def _save_voice_presets(presets: list[dict]):
    tmp = VOICE_PRESETS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, VOICE_PRESETS_PATH)


@app.get("/api/voice-presets")
async def list_voice_presets():
    from scripts.voice_clone import list_voice_profiles
    names = {p["id"]: p.get("name", p["id"]) for p in list_voice_profiles()}
    presets = _load_voice_presets()
    for p in presets:
        p["clone_name"] = names.get(p.get("clone_voice_id") or "", "")
        p["clone_missing"] = bool(p.get("clone_voice_id")) and p["clone_voice_id"] not in names
    return presets


@app.post("/api/voice-presets")
async def save_voice_preset(request: Request):
    body = await request.json()
    name = (body.get("name") or "").strip()[:60]
    if not name:
        return JSONResponse({"error": "กรุณาตั้งชื่อชุดเสียง"}, status_code=400)
    preset = {
        "id": _uuid.uuid4().hex[:8],
        "name": name,
        "voice": body.get("voice") if body.get("voice") in ("female", "male") else "female",
        "rate": max(-50, min(50, int(body.get("rate", 0)))),
        "pitch": max(-50, min(50, int(body.get("pitch", 0)))),
        "tone": body.get("tone") or "normal",
        "tone_custom": body.get("tone_custom") if body.get("tone") == "custom" else None,
        "clone_voice_id": body.get("clone_voice_id") or "",
        "clone_engine": body.get("clone_engine") if body.get("clone_engine") in ("openvoice", "f5-tts-thai") else "openvoice",
        "tau": max(10, min(80, int(body.get("tau", 30)))),
        "source": body.get("source") or "settings",
        "created_at": time.time(),
    }
    presets = [p for p in _load_voice_presets() if p.get("name") != name]
    presets.append(preset)
    _save_voice_presets(presets)
    return preset


@app.delete("/api/voice-presets/{preset_id}")
async def delete_voice_preset(preset_id: str):
    presets = _load_voice_presets()
    kept = [p for p in presets if p.get("id") != preset_id]
    if len(kept) == len(presets):
        return JSONResponse({"error": "Not found"}, status_code=404)
    _save_voice_presets(kept)
    return {"ok": True}


@app.post("/api/script/normalize")
async def normalize_script_text(request: Request):
    from scripts.script_tools import normalize_script

    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "ไม่มีข้อความ"}, status_code=400)
    scenes = max(1, min(20, int(body.get("scenes") or 4)))
    return await normalize_script(text[:6000], scenes)


# ── Replacements endpoints ──


@app.get("/api/replacements")
async def get_replacements():
    from scripts.generate_audio import load_replacements
    return load_replacements()


@app.post("/api/replacements")
async def save_replacements(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"error": "Expected JSON object"}, status_code=400)
    config_dir = BASE_DIR / "config"
    config_dir.mkdir(exist_ok=True)
    with open(config_dir / "replacements.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)
    return {"ok": True, "count": len(body)}


# ── Pexels search endpoints ──


@app.get("/api/pexels/search")
async def search_pexels(
    q: str = Query(..., min_length=1),
    media_type: str = Query("video"),
    orientation: str = Query("portrait"),
):
    from scripts.fetch_images import (
        _pick_best_video_file,
        _search_pexels_photos,
        _search_pexels_videos,
        photo_download_url,
    )

    orient = orientation if orientation in ("portrait", "landscape") else "portrait"
    if media_type == "video":
        results = await asyncio.to_thread(_search_pexels_videos, q, 8, orient)
        items = []
        for v in results:
            dl_url = _pick_best_video_file(v, orient)
            if dl_url:
                items.append({
                    "id": v.get("id"),
                    "type": "video",
                    "thumbnail": v.get("image", ""),
                    "download_url": dl_url,
                    "duration": v.get("duration"),
                })
        return items
    else:
        results = await asyncio.to_thread(_search_pexels_photos, q, 8, orient)
        items = []
        for p in results:
            src = p.get("src", {})
            dl_url = photo_download_url(p, orient)
            thumb = src.get("medium") or src.get("small", "")
            if dl_url:
                items.append({
                    "id": p.get("id"),
                    "type": "image",
                    "thumbnail": thumb,
                    "download_url": dl_url,
                })
        return items


@app.post("/api/pexels/download")
async def download_pexels_media(
    url: str = Query(...),
    media_type: str = Query("video"),
):
    from scripts.fetch_images import _download_file

    UPLOAD_DIR.mkdir(exist_ok=True)
    ext = ".mp4" if media_type == "video" else ".jpg"
    safe_name = f"pexels_{_uuid.uuid4().hex[:8]}{ext}"
    out_path = str(UPLOAD_DIR / safe_name)
    ok = await asyncio.to_thread(_download_file, url, out_path)
    if ok:
        return {"filename": safe_name, "type": media_type, "ok": True}
    return JSONResponse({"error": "Download failed"}, status_code=500)


# ── URL scrape endpoints ──


_BROWSER_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


def _http_get(url: str, timeout: int, limit: int) -> tuple[bytes, str]:
    import urllib.request
    req = urllib.request.Request(url, headers=_BROWSER_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(limit), resp.headers.get("Content-Type", "")


@app.get("/api/url/scrape")
async def scrape_url_images(url: str = Query(..., min_length=1)):
    import urllib.parse
    from bs4 import BeautifulSoup

    try:
        raw, _ = await asyncio.to_thread(_http_get, url, 15, 5_000_000)
        html = raw.decode("utf-8", errors="replace")
    except Exception as e:
        return JSONResponse({"error": f"ไม่สามารถเข้าถึง URL: {e}"}, status_code=400)

    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    items = []

    _IMG_EXTS = re.compile(r"\.(jpe?g|png|webp|avif|bmp|tiff?)(\?|$)", re.I)
    _VID_EXTS = re.compile(r"\.(mp4|webm|mov|avi)(\?|$)", re.I)

    def _add(src: str, media_type: str = "image"):
        if not src or src.startswith("data:"):
            return
        absolute = urllib.parse.urljoin(url, src)
        if absolute in seen:
            return
        seen.add(absolute)
        low = absolute.lower()
        parsed_path = urllib.parse.urlparse(absolute).path.lower()
        if parsed_path.endswith((".svg", ".ico", ".gif")):
            return
        if re.search(r"(favicon|icon|logo|sprite|pixel|tracker|badge|button)", low):
            return
        if media_type == "image" and not _IMG_EXTS.search(absolute):
            return
        if media_type == "video" and not _VID_EXTS.search(absolute):
            return
        items.append(
            {"url": absolute, "thumbnail": absolute, "type": media_type}
        )

    for meta in soup.find_all("meta", property=re.compile(r"og:image|twitter:image")):
        _add(meta.get("content"))

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
        srcset = img.get("srcset") or img.get("data-srcset") or ""
        if srcset:
            candidates = [
                s.strip() for s in srcset.split(",") if s.strip()
            ]
            best = sorted(
                candidates,
                key=lambda s: int(m.group(1))
                if (m := re.search(r"(\d+)w", s))
                else 0,
                reverse=True,
            )
            if best:
                candidate = best[0].strip().split()[0]
                if _IMG_EXTS.search(candidate):
                    src = candidate
        _add(src)

    for vid in soup.find_all("video"):
        poster = vid.get("poster")
        if poster:
            _add(poster)
        for source in vid.find_all("source"):
            _add(source.get("src"), "video")
        vid_src = vid.get("src")
        if vid_src:
            _add(vid_src, "video")

    return items[:40]


@app.get("/api/url/proxy")
async def proxy_image(url: str = Query(...)):
    from fastapi.responses import Response
    try:
        data, content_type = await asyncio.to_thread(_http_get, url, 10, 5_000_000)
        return Response(content=data, media_type=content_type or "image/jpeg")
    except Exception:
        return JSONResponse({"error": "proxy failed"}, status_code=502)


def _download_url_sync(url: str, media_type: str) -> tuple[str, str]:
    import urllib.request
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    ext = ".jpg"
    for k, v in ((".jpeg", ".jpg"), (".jpg", ".jpg"), (".png", ".png"), (".webp", ".webp"),
                 (".mp4", ".mp4"), (".webm", ".webm")):
        if k in path:
            ext = v
            break
    if media_type == "video" and ext not in (".mp4", ".webm"):
        ext = ".mp4"

    req = urllib.request.Request(url, headers=_BROWSER_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        content_type = resp.headers.get("Content-Type", "")
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "mp4" in content_type or "video" in content_type:
            ext = ".mp4"
        safe_name = f"web_{_uuid.uuid4().hex[:8]}{ext}"
        with open(UPLOAD_DIR / safe_name, "wb") as f:
            shutil.copyfileobj(resp, f, 262144)
    return safe_name, "video" if ext in (".mp4", ".webm") else "image"


@app.post("/api/url/download")
async def download_url_media(url: str = Query(...), media_type: str = Query("image")):
    UPLOAD_DIR.mkdir(exist_ok=True)
    try:
        safe_name, ftype = await asyncio.to_thread(_download_url_sync, url, media_type)
        return {"filename": safe_name, "type": ftype, "ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ── TTS engine endpoints ──


@app.get("/api/clone-engines")
async def get_clone_engines():
    from scripts.tts_engines import list_clone_engines
    return list_clone_engines()


# ── Voice clone endpoints ──


_AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".ogg", ".flac"}


@app.get("/api/voices")
async def list_voices():
    from scripts.voice_clone import list_voice_profiles
    return list_voice_profiles()


@app.post("/api/voices/upload")
async def upload_voice(
    file: UploadFile = File(...),
    name: str = Query("My Voice"),
):
    ext = Path(file.filename or "voice.wav").suffix.lower()
    if ext not in _AUDIO_TYPES:
        return JSONResponse({"error": "Unsupported audio format"}, status_code=400)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return JSONResponse({"error": "File too large (max 50MB)"}, status_code=400)
    from scripts.voice_clone import save_voice_profile
    profile = save_voice_profile(content, file.filename or "voice.wav", name)
    return profile


@app.delete("/api/voices/{voice_id}")
async def delete_voice(voice_id: str):
    if "/" in voice_id or "\\" in voice_id or ".." in voice_id:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    from scripts.voice_clone import delete_voice_profile
    if delete_voice_profile(voice_id):
        return {"ok": True}
    return JSONResponse({"error": "Not found"}, status_code=404)


@app.get("/api/voices/{voice_id}/preview")
async def preview_voice(voice_id: str):
    if "/" in voice_id or "\\" in voice_id or ".." in voice_id:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    from scripts.voice_clone import get_reference_path
    ref = get_reference_path(voice_id)
    if not ref:
        return JSONResponse({"error": "Not found"}, status_code=404)
    ext = Path(ref).suffix.lower()
    media = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
             ".ogg": "audio/ogg", ".flac": "audio/flac"}.get(ext, "audio/wav")
    return FileResponse(ref, media_type=media)


# ── Compare all cloned voices ──
# Loads OpenVoice once and reuses it across every saved profile instead of
# spawning one subprocess per voice (~40s each) -- the model load and the
# base-audio tone extraction are identical work regardless of which voice
# comes next, so batching them cuts an 11-voice comparison from minutes to
# roughly one model load plus a few seconds per voice.

_compare_jobs: dict[str, dict] = {}
_COMPARE_TEXT_LIMIT = 150  # keeps every one of the N conversions short
_COMPARE_JOB_TTL = 3600


def _run_compare_job_sync(job_id: str, jobs: list[tuple[str, str, str]], base_wav: str, tau: float):
    import threading
    from scripts.voice_clone import start_clone_batch_process

    job = _compare_jobs[job_id]
    try:
        proc = start_clone_batch_process(base_wav, jobs, tau=tau)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        return

    # A hung child would otherwise leave the job "running" forever.
    watchdog = threading.Timer(120 + 60 * len(jobs), proc.kill)
    watchdog.start()
    try:
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("VOICE_DONE:"):
                vid = line.split(":", 1)[1]
                if vid in job["results"]:
                    job["results"][vid]["status"] = "done"
            elif line.startswith("VOICE_FAIL:"):
                _, vid, err = line.split(":", 2)
                if vid in job["results"]:
                    job["results"][vid]["status"] = "error"
                    job["results"][vid]["error"] = err[:150]
            elif line == "BATCH_DONE":
                break
        proc.wait(timeout=30)
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        proc.kill()
        return
    finally:
        watchdog.cancel()

    # Any voice never resolved (crash mid-batch) shouldn't hang the UI forever.
    for r in job["results"].values():
        if r["status"] == "pending":
            r["status"] = "error"
            r["error"] = "ไม่สำเร็จ (batch หยุดกลางคัน)"

    job["status"] = "done"


@app.post("/api/compare-voices")
async def start_compare_voices(request: Request):
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "กรุณาใส่ข้อความ"}, status_code=400)
    text = text[:_COMPARE_TEXT_LIMIT]

    venv_python = BASE_DIR / ".venv-clone" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return JSONResponse({"error": "OpenVoice ยังไม่ได้ติดตั้ง (.venv-clone)"}, status_code=400)

    from scripts.voice_clone import list_voice_profiles, get_reference_path
    from scripts.generate_audio import (
        VOICES, _tts_with_retry, _clean_script_for_tts,
        apply_replacements, load_replacements,
    )

    profiles = list_voice_profiles()
    if not profiles:
        return JSONResponse({"error": "ไม่มีเสียงโคลนที่บันทึกไว้"}, status_code=400)

    selected_ids = body.get("voice_ids")
    tau = max(0.1, min(0.8, float(body.get("tau", 0.3))))

    cutoff = time.time() - _COMPARE_JOB_TTL
    for old_id in [k for k, j in _compare_jobs.items()
                   if j["status"] != "running" and j["created_at"] < cutoff]:
        del _compare_jobs[old_id]

    job_id = _uuid.uuid4().hex[:8]
    compare_dir = UPLOAD_DIR / "compare" / job_id
    compare_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    jobs = []
    for p in profiles:
        vid = p.get("id", "")
        if selected_ids and vid not in selected_ids:
            continue
        ref_path = get_reference_path(vid)
        if not vid or not ref_path:
            continue
        results[vid] = {"id": vid, "name": p.get("name", vid), "status": "pending", "error": None}
        jobs.append((vid, ref_path, str(compare_dir / f"{vid}.wav")))

    if not jobs:
        return JSONResponse({"error": "ไม่มีเสียงโคลนที่ใช้ได้"}, status_code=400)

    _compare_jobs[job_id] = {
        "status": "running", "results": results, "error": None,
        "created_at": time.time(),
    }

    processed = apply_replacements(_clean_script_for_tts(text), load_replacements())
    mp3_path = str(compare_dir / "base.mp3")
    await _tts_with_retry(processed, VOICES["female"], mp3_path, "+0%", "+0Hz")
    base_wav = str(compare_dir / "base.wav")
    await asyncio.to_thread(_to_wav_48k, mp3_path, base_wav)

    _spawn(asyncio.to_thread(_run_compare_job_sync, job_id, jobs, base_wav, tau))
    return {"job_id": job_id, "total": len(jobs)}


@app.get("/api/compare-voices/status/{job_id}")
async def compare_voices_status(job_id: str):
    job = _compare_jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return {"status": job["status"], "error": job.get("error"), "results": list(job["results"].values())}


@app.get("/api/compare-voices/audio/{job_id}/{voice_id}")
async def compare_voices_audio(job_id: str, voice_id: str):
    if any(c in job_id + voice_id for c in ("/", "\\", "..")):
        return JSONResponse({"error": "Invalid"}, status_code=400)
    path = UPLOAD_DIR / "compare" / job_id / f"{voice_id}.wav"
    if not path.exists():
        return JSONResponse({"error": "Not ready"}, status_code=404)
    return FileResponse(str(path), media_type="audio/wav")


@app.delete("/api/compare-voices/clear")
async def clear_compare_voices():
    for job_id, job in list(_compare_jobs.items()):
        if job["status"] != "running":
            shutil.rmtree(UPLOAD_DIR / "compare" / job_id, ignore_errors=True)
            del _compare_jobs[job_id]
    return {"ok": True}


DRAFTS_DIR = BASE_DIR / "drafts"
DRAFTS_DIR.mkdir(exist_ok=True)


@app.get("/api/drafts")
async def list_drafts():
    drafts = []
    for f in sorted(DRAFTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            drafts.append({
                "id": f.stem,
                "topic": data.get("topic", ""),
                "saved_at": data.get("saved_at", ""),
                "mode": data.get("mode", "narration"),
                "tone": data.get("tone", ""),
            })
        except Exception:
            pass
    return drafts


@app.post("/api/drafts/save")
async def save_draft(request: Request):
    data = await request.json()
    from datetime import datetime
    data["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    draft_id = data.get("id") or _uuid.uuid4().hex[:8]
    data["id"] = draft_id
    path = DRAFTS_DIR / f"{draft_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": draft_id, "saved_at": data["saved_at"]}


@app.get("/api/drafts/{draft_id}")
async def load_draft(draft_id: str):
    if "/" in draft_id or "\\" in draft_id or ".." in draft_id:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    path = DRAFTS_DIR / f"{draft_id}.json"
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return json.loads(path.read_text(encoding="utf-8"))


@app.delete("/api/drafts/{draft_id}")
async def delete_draft(draft_id: str):
    if "/" in draft_id or "\\" in draft_id or ".." in draft_id:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    path = DRAFTS_DIR / f"{draft_id}.json"
    if path.exists():
        path.unlink()
    return {"ok": True}


# ── Visual templates ──

TEMPLATES_DIR = UPLOAD_DIR / "templates"


@app.get("/api/templates")
async def list_templates():
    from scripts.templates import list_templates
    return list_templates()


@app.post("/api/templates/render")
async def render_template(request: Request):
    from scripts.templates import get_template, render_image_template

    form = await request.form()
    template_id = form.get("template_id", "")
    tpl = get_template(template_id)
    if not tpl:
        return JSONResponse({"error": "ไม่พบเทมเพลตนี้"}, status_code=404)

    try:
        fields = json.loads(form.get("fields", "{}"))
    except Exception:
        return JSONResponse({"error": "fields ไม่ใช่ JSON ที่ถูกต้อง"}, status_code=400)

    job_id = _uuid.uuid4().hex[:8]
    job_dir = TEMPLATES_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    photo_paths = {}
    for p in tpl["photos"]:
        key = p["key"]
        upload = form.get(key)
        if upload is None or not hasattr(upload, "read"):
            return JSONResponse({"error": f"ขาดรูปภาพ: {p['label']}"}, status_code=400)
        ext = Path(upload.filename or "photo.jpg").suffix.lower() or ".jpg"
        if ext not in _MEDIA_TYPES:
            return JSONResponse({"error": f"ไฟล์ {p['label']} ไม่ใช่รูปภาพที่รองรับ"}, status_code=400)
        dest = job_dir / f"{key}{ext}"
        content = await upload.read()
        with open(dest, "wb") as f:
            f.write(content)
        photo_paths[key] = str(dest)

    out_path = str(job_dir / "output.png")
    try:
        await asyncio.to_thread(render_image_template, template_id, photo_paths, fields, out_path)
    except Exception as e:
        return JSONResponse({"error": f"สร้างภาพไม่สำเร็จ: {e}"}, status_code=500)

    return {"ok": True, "job_id": job_id, "url": f"/api/templates/image/{job_id}"}


@app.get("/api/templates/image/{job_id}")
async def get_template_image(job_id: str):
    if "/" in job_id or "\\" in job_id or ".." in job_id:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    path = TEMPLATES_DIR / job_id / "output.png"
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(str(path), media_type="image/png")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.app:app", host="127.0.0.1", port=5000, reload=True,
                reload_dirs=["app", "core", "scripts"])
