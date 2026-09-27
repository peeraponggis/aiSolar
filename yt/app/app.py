import asyncio
import os
import shutil
import uuid as _uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

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


@app.get("/")
async def root():
    return FileResponse(str(BASE_DIR / "static" / "dashboard.html"))


@app.post("/api/generate")
async def generate_video(
    topic: str = Query(..., min_length=1),
    voice: str = Query("female"),
    rate: str = Query("+0%"),
    pitch: str = Query("+0Hz"),
    media_files: str = Query(""),
    subtitles: str = Query("on"),
    clone_voice_id: str = Query(""),
    persona: str = Query(""),
    custom_script: str = Query(""),
    bgm_file: str = Query(""),
    bgm_volume: int = Query(20),
    aspect_ratio: str = Query("9:16"),
    mode: str = Query("narration"),
    voice_b: str = Query(""),
    tone: str = Query("normal"),
    tone_var: int = Query(0),
    tone_rate: int = Query(0),
    tone_pitch: int = Query(0),
    overlay_text: str = Query(""),
    overlay_font: str = Query("sarabun"),
    overlay_animation: str = Query("static"),
):
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
                if ext in (".mp4", ".mov", ".avi", ".webm"):
                    dest = media_dir / f"{idx:02d}_clip{ext}"
                else:
                    dest = media_dir / f"{idx:02d}_img{ext}"
                shutil.copy2(str(src), str(dest))
                copied += 1
            skip_fetch = copied > 0
    valid_tones = {"normal", "cheerful", "serious", "energetic", "warm", "news", "custom"}
    tone_val = tone if tone in valid_tones else "normal"
    if tone_val == "custom":
        from scripts.generate_audio import TONE_PRESETS
        TONE_PRESETS["custom"] = {
            "base_rate": max(-30, min(30, tone_rate)),
            "base_pitch": max(-30, min(30, tone_pitch)),
            "variation": max(0, min(30, tone_var)),
        }
    vs = VoiceSettings(voice=voice, rate=rate, pitch=pitch, clone_voice_id=clone_voice_id,
                       tone=tone_val)
    if aspect_ratio == "both":
        ratios = ["9:16", "16:9"]
    elif aspect_ratio in ("9:16", "16:9"):
        ratios = [aspect_ratio]
    else:
        ratios = ["9:16"]
    gen_mode = mode if mode in ("narration", "dialogue") else "narration"
    overlay_opts = {}
    if overlay_text.strip():
        valid_fonts = {"sarabun", "kanit", "prompt", "mitr"}
        valid_anims = {"static", "fade", "slide_up"}
        overlay_opts = {
            "overlay_text": overlay_text.strip(),
            "overlay_font": overlay_font if overlay_font in valid_fonts else "sarabun",
            "overlay_animation": overlay_animation if overlay_animation in valid_anims else "static",
        }
    asyncio.create_task(
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
                              overlay_opts=overlay_opts)
    )
    return {"id": project_id, "status": "processing"}


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


@app.get("/api/download/{project_id}")
async def download_video(project_id: str, ratio: str = Query("")):
    output_dir = BASE_DIR / "projects" / project_id / "output"
    if ratio:
        tag = ratio.replace(":", "x")
        path = output_dir / f"final_{tag}.mp4"
    else:
        path = output_dir / "final_9x16.mp4"
        if not path.exists():
            path = output_dir / "final.mp4"
    if not path.exists():
        return JSONResponse({"error": "Video not found"}, status_code=404)
    return FileResponse(str(path), media_type="video/mp4", filename=path.name)


@app.get("/api/audio/{project_id}")
async def download_audio(project_id: str):
    path = BASE_DIR / "projects" / project_id / "audio" / "narration.mp3"
    if not path.exists():
        return JSONResponse({"error": "Audio not found"}, status_code=404)
    return FileResponse(str(path), media_type="audio/mpeg", filename="narration.mp3")


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


@app.post("/api/preview-voice")
async def preview_voice_tts(
    text: str = Query(..., min_length=1),
    voice: str = Query("female"),
    tone: str = Query("normal"),
):
    from scripts.generate_audio import (
        VOICES, TONE_PRESETS, _clean_script_for_tts,
        apply_replacements, load_replacements, _tts_with_retry,
    )

    processed = _clean_script_for_tts(text)
    replacements = load_replacements()
    processed = apply_replacements(processed, replacements)
    if len(processed) > 500:
        processed = processed[:500]

    voice_name = VOICES.get(voice, VOICES["female"])
    preset = TONE_PRESETS.get(tone, TONE_PRESETS["normal"])
    r_val = preset["base_rate"]
    p_val = preset["base_pitch"]
    rate = f"+{r_val}%" if r_val >= 0 else f"{r_val}%"
    pitch = f"+{p_val}Hz" if p_val >= 0 else f"{p_val}Hz"

    preview_dir = UPLOAD_DIR / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    safe = f"preview_{_uuid.uuid4().hex[:8]}.mp3"
    output = str(preview_dir / safe)
    await _tts_with_retry(processed, voice_name, output, rate, pitch)
    return FileResponse(output, media_type="audio/mpeg", filename="preview.mp3")


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
    import json
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
            dl_url = src.get("large2x") or src.get("large", "")
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.app:app", host="127.0.0.1", port=5000, reload=True)
