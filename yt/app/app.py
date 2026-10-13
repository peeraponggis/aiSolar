import asyncio
import json
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
    duration_preset: str = Query("short"),
    clone_tau: int = Query(30),
    media_durations: str = Query(""),
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
    if tone_val == "custom":
        from scripts.generate_audio import TONE_PRESETS
        TONE_PRESETS["custom"] = {
            "base_rate": max(-30, min(30, tone_rate)),
            "base_pitch": max(-30, min(30, tone_pitch)),
            "variation": max(0, min(30, tone_var)),
        }
    valid_presets = {"short", "medium", "long"}
    dur_preset = duration_preset if duration_preset in valid_presets else "short"
    tau_val = max(10, min(80, clone_tau)) / 100.0
    vs = VoiceSettings(voice=voice, rate=rate, pitch=pitch, clone_voice_id=clone_voice_id,
                       tone=tone_val, clone_tau=tau_val)
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
    dur_list = None
    if media_durations:
        try:
            dur_list = [float(d) for d in media_durations.split(",") if d.strip()]
        except ValueError:
            dur_list = None
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


@app.post("/api/project/{project_id}/media/swap")
async def swap_project_media(project_id: str, request: Request):
    body = await request.json()
    a, b = body.get("a", ""), body.get("b", "")
    if not a or not b or a == b:
        return JSONResponse({"error": "Invalid"}, status_code=400)
    media_dir = BASE_DIR / "projects" / project_id / "media"
    path_a, path_b = media_dir / a, media_dir / b
    if not path_a.exists() or not path_b.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    prefix_a = a.split("_", 1)[0]
    prefix_b = b.split("_", 1)[0]
    suffix_a = a[len(prefix_a):]
    suffix_b = b[len(prefix_b):]
    new_a = prefix_b + suffix_a
    new_b = prefix_a + suffix_b
    tmp = media_dir / f"_swap_{a}"
    path_a.rename(tmp)
    path_b.rename(media_dir / new_b)
    tmp.rename(media_dir / new_a)
    return {"ok": True, "a": new_a, "b": new_b}


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
    clone_voice_id: str = Query(""),
    clone_tau: int = Query(30),
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
    safe = f"preview_{_uuid.uuid4().hex[:8]}"
    mp3_output = str(preview_dir / f"{safe}.mp3")
    await _tts_with_retry(processed, voice_name, mp3_output, rate, pitch)

    if clone_voice_id:
        try:
            from scripts.voice_clone import clone_voice, get_reference_path
            from scripts.generate_audio import FFMPEG
            ref_path = get_reference_path(clone_voice_id)
            if ref_path:
                import subprocess as _sp
                wav_base = str(preview_dir / f"{safe}_base.wav")
                _sp.run([
                    FFMPEG, "-y", "-i", mp3_output,
                    "-acodec", "pcm_s16le", "-ar", "48000", wav_base,
                ], capture_output=True, timeout=60)
                wav_out = str(preview_dir / f"{safe}_cloned.wav")
                tau = max(10, min(80, clone_tau)) / 100.0
                await clone_voice(wav_base, ref_path, wav_out, tau=tau)
                for tmp in (mp3_output, wav_base):
                    if os.path.exists(tmp):
                        os.remove(tmp)
                return FileResponse(wav_out, media_type="audio/wav", filename="preview.wav")
        except Exception as e:
            print(f"Voice clone preview failed: {e}")

    return FileResponse(mp3_output, media_type="audio/mpeg", filename="preview.mp3")


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


# ── URL scrape endpoints ──


@app.get("/api/url/scrape")
async def scrape_url_images(url: str = Query(..., min_length=1)):
    import re
    import urllib.parse
    import urllib.request

    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read(5_000_000).decode("utf-8", errors="replace")
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
    import urllib.request

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            data = resp.read(5_000_000)
        from fastapi.responses import Response
        return Response(content=data, media_type=content_type)
    except Exception:
        return JSONResponse({"error": "proxy failed"}, status_code=502)


@app.post("/api/url/download")
async def download_url_media(
    url: str = Query(...),
    media_type: str = Query("image"),
):
    import urllib.request

    UPLOAD_DIR.mkdir(exist_ok=True)
    ext_map = {
        ".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png",
        ".webp": ".webp", ".mp4": ".mp4", ".webm": ".webm",
    }
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    ext = ".jpg"
    for k, v in ext_map.items():
        if k in path:
            ext = v
            break
    if media_type == "video":
        ext = ".mp4" if ".mp4" in path else ".webm" if ".webm" in path else ".mp4"

    safe_name = f"web_{_uuid.uuid4().hex[:8]}{ext}"
    out_path = str(UPLOAD_DIR / safe_name)
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                )
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"
            elif "mp4" in content_type or "video" in content_type:
                ext = ".mp4"
            if ext != out_path[-len(ext):]:
                safe_name = f"web_{_uuid.uuid4().hex[:8]}{ext}"
                out_path = str(UPLOAD_DIR / safe_name)
            with open(out_path, "wb") as f:
                while True:
                    chunk = resp.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
        ftype = "video" if ext in (".mp4", ".webm") else "image"
        return {"filename": safe_name, "type": ftype, "ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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


@app.post("/api/notification/regenerate")
async def regenerate_notification():
    from scripts.generate_audio import VOICES, TONE_PRESETS, _tts_with_retry

    text = "สร้างคลิป แล้ว ค้าาาาา"
    voice_name = VOICES["female"]
    preset = TONE_PRESETS["cheerful"]
    rate = f"+{preset['base_rate']}%" if preset["base_rate"] >= 0 else f"{preset['base_rate']}%"
    pitch = f"+{preset['base_pitch']}Hz" if preset["base_pitch"] >= 0 else f"{preset['base_pitch']}Hz"

    out_dir = BASE_DIR / "static" / "sounds"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = str(out_dir / "clip_done.mp3")

    try:
        await _tts_with_retry(text, voice_name, out_path, rate, pitch, tone="cheerful")
        return {"ok": True, "size": os.path.getsize(out_path)}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.app:app", host="127.0.0.1", port=5000, reload=True)
