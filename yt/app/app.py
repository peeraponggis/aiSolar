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
    duration_preset: str = Query("short"),
    clone_tau: int = Query(30),
    media_durations: str = Query(""),
    clone_engine: str = Query("openvoice"),
    template_fields: str = Query(""),
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
    _spawn(
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
                              media_durations=dur_list)
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
    Files in `order` come first in that order; any others are numbered after
    them, so two files never share a number."""
    media_dir = BASE_DIR / "projects" / project_id / "media"
    present = sorted(f.name for f in media_dir.iterdir()
                     if f.is_file() and re.match(r"\d+_(clip|img)", f.name))
    ordered = [f for f in order if f in present] + [f for f in present if f not in order]
    staged = []
    for i, fname in enumerate(ordered):
        src = media_dir / fname
        tmp = media_dir / f"__reorder_{i:03d}{src.suffix}"
        os.replace(src, tmp)
        kind = "clip" if src.suffix.lower() in VIDEO_EXTS else "img"
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
    if body.get("media_order"):
        _apply_media_order(project_id, body["media_order"])
    if "media_durations" in body and status.render_params:
        status.render_params["media_durations"] = body["media_durations"] or None

    status.update("creating_video", 82, error=None)
    _spawn(orchestrator.render_video(project_id))
    return {"ok": True}


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
