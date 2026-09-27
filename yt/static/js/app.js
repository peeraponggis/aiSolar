let currentProjectId = null;
let pollTimer = null;
let selectedVoice = "female";
let subtitlesEnabled = true;
let selectedMedia = [];
let mediaExpanded = true;
let cloneVoiceId = "";
let scriptExpanded = false;
let bgmExpanded = false;
let selectedMode = "narration";
let selectedVoiceB = "male";
let selectedTone = "cheerful";
let selectedAspectRatios = ["9:16"];
let bgmFilename = "";
let consoleExpanded = false;
let logLastTimestamp = 0;
let generateStartTime = null;
let _pollingLogs = false;
let unseenLogCount = 0;

const PHASE_LABELS = {
  pending: "รอเริ่ม...",
  brainstorming: "กำลังระดมสมอง (Gemini)...",
  script_done: "ได้สคริปต์แล้ว",
  generating_audio: "กำลังสร้างเสียง (edge-tts)...",
  audio_done: "ได้เสียงแล้ว",
  cloning_voice: "กำลังโคลนเสียง (OpenVoice)...",
  creating_video: "กำลังสร้างวิดีโอ + ซับไตเติ้ล (FFmpeg)...",
  done: "เสร็จสิ้น!",
  error: "เกิดข้อผิดพลาด",
};

// ── Console & ETA ──

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

function toggleConsole() {
  consoleExpanded = !consoleExpanded;
  document.getElementById("consolePanel").classList.toggle("collapsed", !consoleExpanded);
  if (consoleExpanded) {
    unseenLogCount = 0;
    updateConsoleBadge();
    const logs = document.getElementById("consoleLogs");
    logs.scrollTop = logs.scrollHeight;
  }
}

function clearConsole() {
  document.getElementById("consoleLogs").innerHTML = "";
  logLastTimestamp = 0;
  unseenLogCount = 0;
  updateConsoleBadge();
}

function updateConsoleBadge() {
  const badge = document.getElementById("consoleBadge");
  if (unseenLogCount > 0) {
    badge.textContent = unseenLogCount;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

async function pollLogs() {
  if (!currentProjectId || _pollingLogs) return;
  _pollingLogs = true;
  try {
    const resp = await fetch(`/api/logs/${currentProjectId}?after=${logLastTimestamp}`);
    const entries = await resp.json();
    if (!entries.length) return;
    const container = document.getElementById("consoleLogs");
    for (const entry of entries) {
      const div = document.createElement("div");
      div.className = `console-entry ${entry.level || "info"}`;
      const t = new Date(entry.t * 1000);
      const ts = t.toLocaleTimeString("th-TH", { hour12: false });
      div.innerHTML = `<span class="console-time">${ts}</span><span class="console-msg">${escapeHtml(entry.msg)}</span>`;
      container.appendChild(div);
      logLastTimestamp = entry.t;
    }
    container.scrollTop = container.scrollHeight;
    if (!consoleExpanded) {
      unseenLogCount += entries.length;
      updateConsoleBadge();
    }
  } catch {
  } finally {
    _pollingLogs = false;
  }
}

function updateEta(progress) {
  const el = document.getElementById("etaText");
  if (!generateStartTime || progress <= 0) {
    el.textContent = "";
    return;
  }
  const elapsed = (Date.now() - generateStartTime) / 1000;
  if (progress >= 100) {
    el.textContent = `ใช้เวลา ${formatTime(elapsed)}`;
    return;
  }
  const remaining = (elapsed / progress) * (100 - progress);
  el.textContent = `${formatTime(elapsed)} | เหลือ ~${formatTime(remaining)}`;
}

function selectVoice(voice) {
  selectedVoice = voice;
  document.querySelectorAll("[data-voice]").forEach((b) => {
    b.classList.toggle("active", b.dataset.voice === voice);
  });
}

function getRateValue() {
  const v = parseInt(document.getElementById("rateSlider").value);
  return v >= 0 ? `+${v}%` : `${v}%`;
}

function getPitchValue() {
  const v = parseInt(document.getElementById("pitchSlider").value);
  return v >= 0 ? `+${v}Hz` : `${v}Hz`;
}

function updateRateLabel() {
  const v = parseInt(document.getElementById("rateSlider").value);
  const label = document.getElementById("rateLabel");
  if (v === 0) label.textContent = "ปกติ";
  else if (v > 0) label.textContent = `เร็ว +${v}%`;
  else label.textContent = `ช้า ${v}%`;
}

function updatePitchLabel() {
  const v = parseInt(document.getElementById("pitchSlider").value);
  const label = document.getElementById("pitchLabel");
  if (v === 0) label.textContent = "ปกติ";
  else if (v > 0) label.textContent = `สูง +${v}Hz`;
  else label.textContent = `ต่ำ ${v}Hz`;
}

function toggleSubtitles(mode) {
  subtitlesEnabled = mode === "on";
  document.querySelectorAll("[data-subs]").forEach((b) => {
    b.classList.toggle("active", b.dataset.subs === mode);
  });
}

function selectTone(value) {
  selectedTone = value;
  const customRow = document.getElementById("customToneRow");
  if (value === "custom") {
    customRow.classList.remove("hidden");
  } else {
    customRow.classList.add("hidden");
  }
}

function selectMode(mode) {
  selectedMode = mode;
  document.querySelectorAll("[data-mode]").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode);
  });
  const voiceBRow = document.getElementById("dialogueVoiceRow");
  const scriptInput = document.getElementById("customScriptInput");
  if (mode === "dialogue") {
    voiceBRow.classList.remove("hidden");
    scriptInput.placeholder = "B: ทำไม Ollama ถึงเปลี่ยนเกม?\nA: เพราะรัน AI ฟรีบนเครื่องตัวเอง\nB: แล้วมันเร็วแค่ไหน?\nA: 39 โทเค็นต่อวินาที ออฟไลน์ได้ด้วย";
  } else {
    voiceBRow.classList.add("hidden");
    scriptInput.placeholder = "ใส่สคริปต์ที่ต้องการ (ไม่บังคับ)";
  }
}

function selectVoiceB(voice) {
  selectedVoiceB = voice;
  document.querySelectorAll("[data-voiceb]").forEach((b) => {
    b.classList.toggle("active", b.dataset.voiceb === voice);
  });
}

// ── Script & Persona ──

function toggleScriptSection() {
  scriptExpanded = !scriptExpanded;
  document.getElementById("scriptInputContent").classList.toggle("collapsed", !scriptExpanded);
  document.getElementById("scriptToggle").innerHTML = scriptExpanded ? "&#9650;" : "&#9660;";
}

// ── BGM management ──

function toggleBgmSection() {
  bgmExpanded = !bgmExpanded;
  document.getElementById("bgmContent").classList.toggle("collapsed", !bgmExpanded);
  document.getElementById("bgmToggle").innerHTML = bgmExpanded ? "&#9650;" : "&#9660;";
}

function updateScriptCounter() {
  const el = document.getElementById("scriptCounter");
  const text = document.getElementById("customScriptInput").value.trim();
  if (!text) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  const cleaned = text.replace(/\[.*?\]/g, "").replace(/[—\-–]+/g, " ").trim();
  const chars = cleaned.length;
  const thaiRate = 8;
  const estSec = Math.round(chars / thaiRate);
  el.className = "script-counter" + (estSec > 60 ? " over" : estSec > 50 ? " warn" : "");
  const icon = estSec > 60 ? "!!" : estSec > 50 ? "!" : "";
  el.innerHTML = `<span>${chars} ตัวอักษร</span><span>~${estSec} วินาที ${icon}</span>`;
}

function toggleAspectRatio(ratio) {
  const idx = selectedAspectRatios.indexOf(ratio);
  if (idx >= 0) {
    if (selectedAspectRatios.length <= 1) return;
    selectedAspectRatios.splice(idx, 1);
  } else {
    selectedAspectRatios.push(ratio);
  }
  document.querySelectorAll(".aspect-btn").forEach(b => {
    b.classList.toggle("active", selectedAspectRatios.includes(b.dataset.ratio));
  });
  updateMediaAspectRatio();
}

function updateMediaAspectRatio() {
  const primary = selectedAspectRatios[0] || "9:16";
  const isLandscape = primary === "16:9";
  const grid = document.getElementById("mediaGrid");
  if (grid) grid.classList.toggle("ratio-landscape", isLandscape);
  const pexels = document.getElementById("pexelsResults");
  if (pexels) pexels.classList.toggle("ratio-landscape", isLandscape);
}

function switchVideoRatio(projectId, ratio, btn) {
  const url = `/api/download/${projectId}?ratio=${encodeURIComponent(ratio)}`;
  const player = document.getElementById("videoPlayer");
  player.src = url;
  if (ratio === "16:9") {
    player.width = 480; player.height = 270;
  } else {
    player.width = 270; player.height = 480;
  }
  document.querySelectorAll(".ratio-tab").forEach(t => t.classList.remove("active"));
  btn.classList.add("active");
}

function updateBgmVolumeLabel() {
  const v = document.getElementById("bgmVolumeSlider").value;
  document.getElementById("bgmVolumeLabel").textContent = v + "%";
}

async function uploadBgm(fileList) {
  if (!fileList || !fileList.length) return;
  const formData = new FormData();
  formData.append("files", fileList[0]);
  showToast("กำลังอัปโหลดเสียงประกอบ...");
  try {
    const resp = await fetch("/api/upload", { method: "POST", body: formData });
    const saved = await resp.json();
    if (saved.length) {
      bgmFilename = saved[0].filename;
      document.getElementById("bgmFileName").textContent = fileList[0].name;
      document.getElementById("bgmPlayer").src = `/api/uploads/file/${bgmFilename}`;
      document.getElementById("bgmEmpty").classList.add("hidden");
      document.getElementById("bgmPreview").classList.remove("hidden");
      showToast("อัปโหลดเสียงประกอบสำเร็จ");
    } else {
      showToast("ไม่รองรับไฟล์ประเภทนี้", true);
    }
  } catch (e) {
    showToast("อัปโหลดไม่สำเร็จ", true);
  }
  document.getElementById("bgmFileInput").value = "";
}

async function removeBgm() {
  if (bgmFilename) {
    try { await fetch(`/api/uploads/${bgmFilename}`, { method: "DELETE" }); } catch {}
  }
  bgmFilename = "";
  document.getElementById("bgmEmpty").classList.remove("hidden");
  document.getElementById("bgmPreview").classList.add("hidden");
  document.getElementById("bgmPlayer").src = "";
}

// ── Media management ──

function toggleMediaSection() {
  mediaExpanded = !mediaExpanded;
  document.getElementById("mediaContent").classList.toggle("collapsed", !mediaExpanded);
  document.getElementById("mediaToggle").innerHTML = mediaExpanded ? "&#9650;" : "&#9660;";
}

async function searchPexels() {
  const query = document.getElementById("pexelsQuery").value.trim();
  if (!query) return;
  const type = document.getElementById("pexelsType").value;
  const grid = document.getElementById("pexelsResults");
  grid.innerHTML = '<p class="loading">กำลังค้นหา...</p>';
  try {
    const orientation = (selectedAspectRatios[0] || "9:16") === "16:9" ? "landscape" : "portrait";
    const resp = await fetch(
      `/api/pexels/search?q=${encodeURIComponent(query)}&media_type=${type}&orientation=${orientation}`
    );
    if (!resp.ok) {
      grid.innerHTML = '<p class="no-results">ค้นหาไม่สำเร็จ</p>';
      return;
    }
    const items = await resp.json();
    if (!items.length) {
      grid.innerHTML = '<p class="no-results">ไม่พบผลลัพธ์</p>';
      return;
    }
    grid.innerHTML = items
      .map(
        (item, i) => `
      <div class="pexels-item" onclick="addPexelsMedia(${i})" data-index="${i}">
        <img src="${item.thumbnail}" alt="" loading="lazy">
        <span class="pexels-badge">${
          item.type === "video" ? "VID " + (item.duration || "") + "s" : "IMG"
        }</span>
      </div>`
      )
      .join("");
    window._pexelsResults = items;
    updateMediaAspectRatio();
  } catch (e) {
    grid.innerHTML = '<p class="no-results">ค้นหาไม่สำเร็จ</p>';
  }
}

async function addPexelsMedia(index) {
  const items = window._pexelsResults;
  if (!items || !items[index]) return;
  const item = items[index];
  const el = document.querySelector(`.pexels-item[data-index="${index}"]`);
  if (el) el.classList.add("downloading");
  try {
    const resp = await fetch(
      `/api/pexels/download?url=${encodeURIComponent(item.download_url)}&media_type=${item.type}`,
      { method: "POST" }
    );
    const data = await resp.json();
    if (data.ok) {
      selectedMedia.push({
        filename: data.filename,
        type: data.type,
        thumbnail: item.thumbnail,
      });
      renderMediaGrid();
      showToast("เพิ่มสื่อสำเร็จ");
    } else {
      showToast("ดาวน์โหลดไม่สำเร็จ", true);
    }
  } catch (e) {
    showToast("ดาวน์โหลดไม่สำเร็จ", true);
  } finally {
    if (el) el.classList.remove("downloading");
  }
}

function handleDrop(e) {
  e.preventDefault();
  const area = e.target.closest(".upload-area");
  if (area) area.classList.remove("dragover");
  handleUpload(e.dataTransfer.files);
}

async function handleUpload(fileList) {
  if (!fileList || !fileList.length) return;
  const formData = new FormData();
  for (const f of fileList) formData.append("files", f);
  showToast("กำลังอัปโหลด...");
  try {
    const resp = await fetch("/api/upload", { method: "POST", body: formData });
    const saved = await resp.json();
    for (const s of saved) {
      selectedMedia.push({
        filename: s.filename,
        type: s.type,
        thumbnail: `/api/uploads/file/${s.filename}`,
      });
    }
    renderMediaGrid();
    showToast(`อัปโหลดสำเร็จ ${saved.length} ไฟล์`);
  } catch (e) {
    showToast("อัปโหลดไม่สำเร็จ", true);
  }
  document.getElementById("fileInput").value = "";
}

function renderMediaGrid() {
  const container = document.getElementById("selectedMedia");
  const grid = document.getElementById("mediaGrid");
  const count = document.getElementById("mediaCount");
  if (!selectedMedia.length) {
    container.classList.add("hidden");
    return;
  }
  container.classList.remove("hidden");
  count.textContent = selectedMedia.length;
  grid.innerHTML = selectedMedia
    .map(
      (m, i) => `
    <div class="media-item" draggable="true" data-index="${i}">
      ${
        m.type === "video"
          ? `<video src="/api/uploads/file/${m.filename}" preload="metadata" muted></video>`
          : `<img src="${m.thumbnail}" alt="">`
      }
      <span class="media-order">${i + 1}</span>
      <button class="media-remove" onclick="event.stopPropagation();removeMedia(${i})">&#215;</button>
      ${m.type === "video"
        ? `<button class="media-trim" onclick="event.stopPropagation();openTrimTool(${i})" title="ตัดวิดีโอ">&#9988;</button>`
        : `<button class="media-crop" onclick="event.stopPropagation();openCropTool(${i})" title="ครอปรูป">&#9986;</button>`
      }
      <span class="media-type-badge">${m.type === "video" ? "VID" : "IMG"}</span>
    </div>`
    )
    .join("");
  grid.querySelectorAll(".media-item").forEach((item) => {
    item.addEventListener("dragstart", onDragStart);
    item.addEventListener("dragover", onDragOver);
    item.addEventListener("dragenter", onDragEnter);
    item.addEventListener("dragleave", onDragLeave);
    item.addEventListener("drop", onDropItem);
    item.addEventListener("dragend", onDragEnd);
  });
  updateMediaAspectRatio();
}

let _dragIdx = null;
function onDragStart(e) {
  _dragIdx = parseInt(e.currentTarget.dataset.index);
  e.currentTarget.classList.add("dragging");
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", "");
}
function onDragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
}
function onDragEnter(e) {
  e.preventDefault();
  e.currentTarget.classList.add("drag-over");
}
function onDragLeave(e) {
  e.currentTarget.classList.remove("drag-over");
}
function onDropItem(e) {
  e.preventDefault();
  const dropIdx = parseInt(e.currentTarget.dataset.index);
  e.currentTarget.classList.remove("drag-over");
  if (_dragIdx === null || _dragIdx === dropIdx) return;
  const item = selectedMedia.splice(_dragIdx, 1)[0];
  selectedMedia.splice(dropIdx, 0, item);
  _dragIdx = null;
  renderMediaGrid();
}
function onDragEnd(e) {
  e.currentTarget.classList.remove("dragging");
  document
    .querySelectorAll(".drag-over")
    .forEach((el) => el.classList.remove("drag-over"));
}

async function removeMedia(index) {
  const item = selectedMedia[index];
  try {
    await fetch(`/api/uploads/${item.filename}`, { method: "DELETE" });
  } catch {}
  selectedMedia.splice(index, 1);
  renderMediaGrid();
}

async function clearAllMedia() {
  try {
    await fetch("/api/uploads/clear", { method: "POST" });
  } catch {}
  selectedMedia = [];
  renderMediaGrid();
}

// ── Crop Tool ──

let cropImageIndex = null;
let cropRect = null;
let cropImg = null;
let _cropDragging = false;
let _cropStart = null;

function openCropTool(index) {
  cropImageIndex = index;
  const m = selectedMedia[index];
  const url = m.thumbnail || `/api/uploads/file/${m.filename}`;
  const canvas = document.getElementById("cropCanvas");
  const ctx = canvas.getContext("2d");
  cropImg = new Image();
  cropImg.crossOrigin = "anonymous";
  cropImg.onload = () => {
    const maxW = 560, maxH = window.innerHeight * 0.55;
    let scale = Math.min(maxW / cropImg.width, maxH / cropImg.height, 1);
    canvas.width = Math.round(cropImg.width * scale);
    canvas.height = Math.round(cropImg.height * scale);
    cropRect = { x: 0, y: 0, w: canvas.width, h: canvas.height };
    _fitCropToRatio();
    _drawCrop();
    document.getElementById("cropModal").classList.remove("hidden");
  };
  cropImg.src = url;
}

function _getCropRatio() {
  const primary = selectedAspectRatios[0] || "9:16";
  return primary === "16:9" ? 16 / 9 : 9 / 16;
}

function _fitCropToRatio() {
  const canvas = document.getElementById("cropCanvas");
  const ratio = _getCropRatio();
  let w = canvas.width, h = canvas.height;
  if (w / h > ratio) {
    w = Math.round(h * ratio);
  } else {
    h = Math.round(w / ratio);
  }
  cropRect = {
    x: Math.round((canvas.width - w) / 2),
    y: Math.round((canvas.height - h) / 2),
    w, h
  };
}

function _drawCrop() {
  const canvas = document.getElementById("cropCanvas");
  const ctx = canvas.getContext("2d");
  const scale = canvas.width / cropImg.width;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(cropImg, 0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "rgba(0,0,0,0.5)";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.clearRect(cropRect.x, cropRect.y, cropRect.w, cropRect.h);
  ctx.drawImage(cropImg,
    cropRect.x / scale, cropRect.y / scale, cropRect.w / scale, cropRect.h / scale,
    cropRect.x, cropRect.y, cropRect.w, cropRect.h);
  ctx.strokeStyle = "#7c3aed";
  ctx.lineWidth = 2;
  ctx.strokeRect(cropRect.x, cropRect.y, cropRect.w, cropRect.h);
}

document.addEventListener("DOMContentLoaded", () => {
  const canvas = document.getElementById("cropCanvas");
  if (!canvas) return;
  canvas.addEventListener("mousedown", (e) => {
    const rect = canvas.getBoundingClientRect();
    _cropDragging = true;
    _cropStart = { x: e.clientX - rect.left, y: e.clientY - rect.top };
  });
  canvas.addEventListener("mousemove", (e) => {
    if (!_cropDragging || !_cropStart) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const ratio = _getCropRatio();
    let w = Math.abs(mx - _cropStart.x);
    let h = Math.round(w / ratio);
    if (h > canvas.height) { h = canvas.height; w = Math.round(h * ratio); }
    if (w > canvas.width) { w = canvas.width; h = Math.round(w / ratio); }
    let x = Math.min(_cropStart.x, mx);
    let y = Math.min(_cropStart.y, my);
    if (x + w > canvas.width) x = canvas.width - w;
    if (y + h > canvas.height) y = canvas.height - h;
    if (x < 0) x = 0;
    if (y < 0) y = 0;
    cropRect = { x, y, w, h };
    _drawCrop();
  });
  canvas.addEventListener("mouseup", () => { _cropDragging = false; });
  canvas.addEventListener("mouseleave", () => { _cropDragging = false; });
});

function resetCrop() {
  _fitCropToRatio();
  _drawCrop();
}

function closeCrop() {
  document.getElementById("cropModal").classList.add("hidden");
  cropImageIndex = null;
}

async function confirmCrop() {
  if (cropImageIndex === null || !cropImg) return;
  const canvas = document.getElementById("cropCanvas");
  const scale = cropImg.width / canvas.width;
  const sx = Math.round(cropRect.x * scale);
  const sy = Math.round(cropRect.y * scale);
  const sw = Math.round(cropRect.w * scale);
  const sh = Math.round(cropRect.h * scale);

  const offscreen = document.createElement("canvas");
  offscreen.width = sw;
  offscreen.height = sh;
  const octx = offscreen.getContext("2d");
  octx.drawImage(cropImg, sx, sy, sw, sh, 0, 0, sw, sh);

  const blob = await new Promise(r => offscreen.toBlob(r, "image/jpeg", 0.92));
  const form = new FormData();
  form.append("files", blob, "cropped.jpg");
  try {
    const resp = await fetch("/api/upload", { method: "POST", body: form });
    const [uploaded] = await resp.json();
    if (uploaded) {
      const old = selectedMedia[cropImageIndex];
      try { await fetch(`/api/uploads/${old.filename}`, { method: "DELETE" }); } catch {}
      selectedMedia[cropImageIndex] = {
        filename: uploaded.filename,
        type: "image",
        thumbnail: `/api/uploads/file/${uploaded.filename}`,
      };
      renderMediaGrid();
      showToast("ครอปสำเร็จ");
    }
  } catch (e) {
    showToast("ครอปไม่สำเร็จ", true);
  }
  closeCrop();
}

// ── Trim Tool ──

let trimVideoIndex = null;

function openTrimTool(index) {
  trimVideoIndex = index;
  const m = selectedMedia[index];
  const player = document.getElementById("trimPlayer");
  player.src = `/api/uploads/file/${m.filename}`;
  player.onloadedmetadata = () => {
    const dur = player.duration;
    const startEl = document.getElementById("trimStart");
    const endEl = document.getElementById("trimEnd");
    startEl.max = dur;
    endEl.max = dur;
    startEl.value = 0;
    endEl.value = dur;
    updateTrimPreview();
    document.getElementById("trimModal").classList.remove("hidden");
  };
  player.load();
}

function _fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

function updateTrimPreview() {
  const s = parseFloat(document.getElementById("trimStart").value);
  let e = parseFloat(document.getElementById("trimEnd").value);
  if (e <= s + 1) e = s + 1;
  document.getElementById("trimEnd").value = e;
  document.getElementById("trimStartLabel").textContent = _fmtTime(s);
  document.getElementById("trimEndLabel").textContent = _fmtTime(e);
  document.getElementById("trimDuration").textContent = _fmtTime(e - s);
  const player = document.getElementById("trimPlayer");
  if (Math.abs(player.currentTime - s) > 0.5) player.currentTime = s;
}

function closeTrim() {
  document.getElementById("trimModal").classList.add("hidden");
  const player = document.getElementById("trimPlayer");
  player.pause();
  player.src = "";
  trimVideoIndex = null;
}

async function confirmTrim() {
  if (trimVideoIndex === null) return;
  const start = parseFloat(document.getElementById("trimStart").value);
  const end = parseFloat(document.getElementById("trimEnd").value);
  const m = selectedMedia[trimVideoIndex];
  const btn = document.querySelector("#trimModal .generate-btn");
  btn.disabled = true;
  btn.textContent = "กำลังตัด...";
  try {
    const resp = await fetch(
      `/api/uploads/trim?filename=${encodeURIComponent(m.filename)}&start=${start}&end=${end}`,
      { method: "POST" }
    );
    if (!resp.ok) {
      showToast("ตัดไม่สำเร็จ", true);
      return;
    }
    const result = await resp.json();
    if (result.filename) {
      try { await fetch(`/api/uploads/${m.filename}`, { method: "DELETE" }); } catch {}
      selectedMedia[trimVideoIndex] = {
        filename: result.filename,
        type: "video",
        thumbnail: m.thumbnail,
      };
      renderMediaGrid();
      showToast("ตัดวิดีโอสำเร็จ");
    }
  } catch (e) {
    showToast("ตัดไม่สำเร็จ", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "ตัด";
  }
  closeTrim();
}

// ── Generate ──

async function startGenerate() {
  const input = document.getElementById("topicInput");
  const topic = input.value.trim();
  if (!topic) return showToast("กรุณาใส่หัวข้อ", true);

  const btn = document.getElementById("generateBtn");
  btn.disabled = true;
  btn.textContent = "กำลังสร้าง...";

  document.getElementById("progressSection").classList.remove("hidden");
  document.getElementById("resultSection").classList.add("hidden");
  updateProgress(0, "pending");

  generateStartTime = Date.now();
  logLastTimestamp = 0;
  unseenLogCount = 0;
  document.getElementById("consoleLogs").innerHTML = "";
  updateConsoleBadge();
  document.getElementById("etaText").textContent = "";

  const persona = document.getElementById("personaInput").value.trim();
  const customScript = document.getElementById("customScriptInput").value.trim();

  const bgmVolume = document.getElementById("bgmVolumeSlider").value;
  const params = new URLSearchParams({
    topic,
    voice: selectedVoice,
    rate: getRateValue(),
    pitch: getPitchValue(),
    subtitles: subtitlesEnabled ? "on" : "off",
    clone_voice_id: cloneVoiceId,
    persona,
    custom_script: customScript,
    bgm_file: bgmFilename,
    bgm_volume: bgmVolume,
    aspect_ratio: selectedAspectRatios.length > 1 ? "both" : selectedAspectRatios[0],
    mode: selectedMode,
    voice_b: selectedMode === "dialogue" ? selectedVoiceB : "",
    tone: selectedTone,
    tone_var: selectedTone === "custom" ? (document.getElementById("customToneVar").value || 10) : 0,
    tone_rate: selectedTone === "custom" ? (document.getElementById("customToneRate").value || 0) : 0,
    tone_pitch: selectedTone === "custom" ? (document.getElementById("customTonePitch").value || 0) : 0,
    overlay_text: (document.getElementById("overlayTextInput").value || "").trim(),
    overlay_font: document.getElementById("overlayFont").value,
    overlay_animation: document.getElementById("overlayAnimation").value,
  });
  if (selectedMedia.length) {
    params.set("media_files", selectedMedia.map((m) => m.filename).join(","));
  }

  try {
    const resp = await fetch(`/api/generate?${params}`, { method: "POST" });
    const data = await resp.json();
    currentProjectId = data.id;
    pollStatus();
  } catch (e) {
    showToast("เชื่อมต่อเซิร์ฟเวอร์ไม่ได้", true);
    btn.disabled = false;
    btn.textContent = "สร้างคลิป";
  }
}

function pollStatus() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    if (!currentProjectId) return;
    try {
      const resp = await fetch(`/api/status/${currentProjectId}`);
      const data = await resp.json();
      updateProgress(data.progress, data.phase);
      updateEta(data.progress);
      pollLogs();

      if (data.script) {
        document.getElementById("scriptContent").textContent = data.script;
      }

      if (data.phase === "done") {
        clearInterval(pollTimer);
        setTimeout(pollLogs, 500);
        updateEta(100);
        showResult(data);
        resetButton();
        showToast("สร้างคลิปสำเร็จ!");
        loadHistory();
      } else if (data.phase === "error") {
        clearInterval(pollTimer);
        setTimeout(pollLogs, 500);
        updateEta(0);
        showToast(data.error || "เกิดข้อผิดพลาด", true);
        resetButton();
      }
    } catch (e) {
      /* retry silently */
    }
  }, 2000);
}

function updateProgress(percent, phase) {
  document.getElementById("progressBar").style.width = percent + "%";
  document.getElementById("progressPercent").textContent = percent + "%";
  document.getElementById("phaseText").textContent =
    PHASE_LABELS[phase] || phase;
}

function showResult(data) {
  const section = document.getElementById("resultSection");
  section.classList.remove("hidden");
  document.getElementById("progressSection").classList.remove("hidden");

  if (data.script) {
    document.getElementById("scriptContent").textContent = data.script;
  }
  if (data.audio_path) {
    document.getElementById("audioPlayer").src =
      `/api/audio/${data.project_id}`;
  }

  const ratioTabsEl = document.getElementById("ratioTabs");
  const dlContainer = document.getElementById("downloadBtns");
  ratioTabsEl.innerHTML = "";
  dlContainer.innerHTML = "";
  ratioTabsEl.classList.add("hidden");

  const paths = data.video_paths || {};
  const ratios = Object.keys(paths);
  if (!ratios.length && data.video_path) {
    ratios.push("9:16");
  }

  if (ratios.length) {
    const firstRatio = ratios[0];
    const videoUrl = `/api/download/${data.project_id}?ratio=${encodeURIComponent(firstRatio)}`;
    const player = document.getElementById("videoPlayer");
    player.src = videoUrl;
    if (firstRatio === "16:9") {
      player.width = 480; player.height = 270;
    } else {
      player.width = 270; player.height = 480;
    }

    if (ratios.length > 1) {
      ratioTabsEl.classList.remove("hidden");
      const TAB_LABELS = {"9:16": "แนวตั้ง Shorts", "16:9": "แนวนอน YouTube"};
      ratioTabsEl.innerHTML = ratios.map((r, i) =>
        `<button class="ratio-tab ${i===0?'active':''}" onclick="switchVideoRatio('${data.project_id}','${r}',this)">${TAB_LABELS[r] || r}</button>`
      ).join("");
    }

    const RATIO_LABELS = {"9:16": "แนวตั้ง Shorts/Reels/TikTok", "16:9": "แนวนอน YouTube"};
    dlContainer.innerHTML = ratios.map(r => {
      const tag = r.replace(":", "x");
      const url = `/api/download/${data.project_id}?ratio=${encodeURIComponent(r)}`;
      const label = RATIO_LABELS[r] || r;
      return `<a href="${url}" class="download-btn" download="final_${tag}.mp4">&#11015; ${label}</a>`;
    }).join("");
  }

  switchTab("script");
}

function switchTab(name) {
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".tab-content")
    .forEach((c) => c.classList.remove("active"));
  document
    .querySelector(`.tab-content#tab-${name}`)
    ?.classList.add("active");
  document
    .querySelector(`.tab[onclick*="${name}"]`)
    ?.classList.add("active");
}

function resetButton() {
  const btn = document.getElementById("generateBtn");
  btn.disabled = false;
  btn.textContent = "สร้างคลิป";
}

function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.className = "toast show" + (isError ? " error" : "");
  setTimeout(() => (toast.className = "toast"), 3000);
}

async function loadProject(projectId) {
  try {
    const resp = await fetch(`/api/status/${projectId}`);
    const data = await resp.json();
    currentProjectId = projectId;

    updateProgress(data.progress, data.phase);
    document.getElementById("progressSection").classList.remove("hidden");

    if (data.phase === "done") {
      showResult(data);
    }
  } catch (e) {
    showToast("โหลดโปรเจคไม่ได้", true);
  }
}

async function loadHistory() {
  try {
    const resp = await fetch("/api/projects");
    const projects = await resp.json();
    const list = document.getElementById("historyList");
    list.innerHTML = projects
      .reverse()
      .map(
        (p) => `
      <div class="history-item ${p.phase === "done" ? "clickable" : ""}">
        <span class="topic" ${p.phase === "done" ? `onclick="loadProject('${p.project_id}')"` : ""}>${escapeHtml(p.topic)}</span>
        <span class="status ${p.phase}">${
          PHASE_LABELS[p.phase] || p.phase
        }</span>
        ${p.phase === "done" ? `<button class="rebuild-btn" onclick="event.stopPropagation();rebuildProject('${p.project_id}')" title="นำมาสร้างใหม่">&#8635;</button>` : ""}
      </div>`
      )
      .join("");
  } catch (e) {
    /* silent */
  }
}

async function rebuildProject(projectId) {
  try {
    const resp = await fetch(`/api/status/${projectId}`);
    const data = await resp.json();
    if (data.error && !data.topic) {
      showToast("โหลดโปรเจคไม่ได้", true);
      return;
    }
    document.getElementById("topicInput").value = data.topic || "";
    if (data.script) {
      if (!scriptExpanded) toggleScriptSection();
      document.getElementById("customScriptInput").value = data.script;
      updateScriptCounter();
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
    showToast("โหลดโปรเจคเก่าแล้ว — แก้ไขแล้วกด สร้างคลิป");
  } catch (e) {
    showToast("โหลดโปรเจคไม่ได้", true);
  }
}

// ── Voice Clone ──

function selectCloneVoice(voiceId) {
  cloneVoiceId = voiceId;
  const info = document.getElementById("cloneVoiceInfo");
  if (voiceId) {
    info.classList.remove("hidden");
    const sel = document.getElementById("cloneVoiceSelect");
    const opt = sel.options[sel.selectedIndex];
    document.getElementById("cloneVoiceName").textContent = opt.text;
    document.getElementById("clonePreview").src = `/api/voices/${voiceId}/preview`;
  } else {
    info.classList.add("hidden");
  }
}

async function uploadVoiceFile(fileList) {
  if (!fileList || !fileList.length) return;
  const file = fileList[0];
  const name = prompt("ตั้งชื่อเสียงนี้:", file.name.replace(/\.[^.]+$/, ""));
  if (!name) return;
  const formData = new FormData();
  formData.append("file", file);
  showToast("กำลังอัปโหลดเสียง...");
  try {
    const resp = await fetch(`/api/voices/upload?name=${encodeURIComponent(name)}`, {
      method: "POST",
      body: formData,
    });
    const data = await resp.json();
    if (data.id) {
      showToast("อัปโหลดเสียงสำเร็จ");
      await loadVoiceProfiles();
      document.getElementById("cloneVoiceSelect").value = data.id;
      selectCloneVoice(data.id);
    } else {
      showToast(data.error || "อัปโหลดไม่สำเร็จ", true);
    }
  } catch (e) {
    showToast("อัปโหลดไม่สำเร็จ", true);
  }
  document.getElementById("voiceFileInput").value = "";
}

async function removeCloneVoice() {
  if (!cloneVoiceId) return;
  if (!confirm("ลบเสียงโคลนนี้?")) return;
  try {
    await fetch(`/api/voices/${cloneVoiceId}`, { method: "DELETE" });
    showToast("ลบเสียงสำเร็จ");
  } catch {}
  cloneVoiceId = "";
  document.getElementById("cloneVoiceSelect").value = "";
  document.getElementById("cloneVoiceInfo").classList.add("hidden");
  loadVoiceProfiles();
}

async function loadVoiceProfiles() {
  try {
    const resp = await fetch("/api/voices");
    const voices = await resp.json();
    const sel = document.getElementById("cloneVoiceSelect");
    const current = sel.value;
    sel.innerHTML = '<option value="">ไม่ใช้ (ใช้เสียง TTS ปกติ)</option>';
    for (const v of voices) {
      const opt = document.createElement("option");
      opt.value = v.id;
      opt.textContent = `${v.name} (${v.duration}s)`;
      sel.appendChild(opt);
    }
    if (current) sel.value = current;
  } catch {}
}

// ── Help system ──

const HELP_TEXTS = {
  voice: {
    title: "เสียงพูด",
    body: "เลือกเสียง TTS สำหรับบรรยาย\n\n<b>หญิง (เปรมวดี)</b> — เสียง th-TH-PremwadeeNeural\n<b>ชาย (นิวัตน์)</b> — เสียง th-TH-NiwatNeural\n\nถ้าใช้โหมดสนทนา 2 คน เสียงนี้จะเป็น \"เสียง A\" (คนอธิบาย)"
  },
  rate: {
    title: "ความเร็วเสียง",
    body: "ปรับความเร็วในการพูด\n\n<b>0</b> = ปกติ\n<b>+20~30</b> = เร็วขึ้นเล็กน้อย เหมาะกับ Shorts\n<b>-20~30</b> = ช้าลง เน้นชัดเจน"
  },
  pitch: {
    title: "ระดับเสียง (Pitch)",
    body: "ปรับความสูง-ต่ำของเสียง\n\n<b>0</b> = ปกติ\n<b>+</b> = เสียงสูงขึ้น\n<b>-</b> = เสียงต่ำลง\n\nแนะนำ: ค่าเริ่มต้น 0 มักเหมาะสมที่สุด"
  },
  mode: {
    title: "โหมดการเล่าเรื่อง",
    body: "<b>บรรยาย</b> — เสียงเดียวเล่าเรื่องตลอดทั้งคลิป\n\n<b>สนทนา 2 คน</b> — บทสนทนาระหว่าง 2 คน (A = คนอธิบาย, B = คนถาม)\n\nสคริปต์จะถูกสร้างในรูปแบบ:\nB: ทำไม Ollama ถึงเปลี่ยนเกม?\nA: เพราะรัน AI ฟรีบนเครื่องตัวเอง\n\nซับไตเติ้ลจะแสดงคนละสี (A = ขาว, B = เหลือง)"
  },
  voiceb: {
    title: "เสียง B (คู่สนทนา)",
    body: "เลือกเสียงสำหรับ \"คน B\" (คนถาม) ในโหมดสนทนา 2 คน\n\nเสียง A มาจากค่า \"เสียง\" ด้านบน\nเสียง B เลือกที่นี่ — ควรเลือกเพศตรงข้ามกับเสียง A เพื่อให้แยกเสียงชัด"
  },
  subtitles: {
    title: "ซับไตเติ้ล",
    body: "แสดงข้อความซับไตเติ้ลบนวิดีโอ\n\n<b>เปิด</b> — มีซับไทยใต้ภาพ (แนะนำ เพราะคนส่วนใหญ่ดูแบบปิดเสียง)\n<b>ปิด</b> — ไม่มีซับ"
  },
  aspect: {
    title: "อัตราส่วนวิดีโอ",
    body: "<b>แนวตั้ง (9:16)</b> — สำหรับ Shorts/Reels/TikTok\n<b>แนวนอน (16:9)</b> — สำหรับ YouTube\n\nกดเลือกได้ทั้ง 2 อัน = ระบบจะสร้าง 2 ไฟล์ในครั้งเดียว"
  },
  tone: {
    title: "โทนเสียง",
    body: "ปรับอารมณ์/โทนเสียง TTS ให้ไม่ราบเรียบ โดยใช้ SSML prosody variation ต่อประโยค\n\n<b>ปกติ</b> — เสียงราบเรียบแบบดั้งเดิม ไม่มี variation\n<b>สนุกสนาน</b> — เสียงสดใส มีชีวิตชีวา เหมาะกับ content ทั่วไป (แนะนำ)\n<b>ตื่นเต้น</b> — เร็ว กระตือรือร้น เหมาะกับข่าวเทค/เปิดตัวสินค้า\n<b>อบอุ่น</b> — เสียงนุ่มนวล เป็นกันเอง เหมาะกับ tutorial\n<b>จริงจัง</b> — เสียงหนักแน่น ช้าลงเล็กน้อย เหมาะกับเนื้อหาวิชาการ\n<b>ผู้ประกาศข่าว</b> — จังหวะชัดเจน เหมาะกับรายงานข่าว\n<b>กำหนดเอง</b> — ปรับค่า variation, rate offset, pitch offset ตามต้องการ"
  },
  clone: {
    title: "โคลนเสียง (OpenVoice V2)",
    body: "ใช้ AI โคลนน้ำเสียงจากไฟล์เสียงที่อัปโหลด\n\n<b>วิธีใช้:</b>\n1. กด \"+ อัปโหลดเสียง\" เลือกไฟล์เสียง (.wav/.mp3/.m4a) ที่มีเสียงพูดชัดๆ ยาว 5-30 วินาที\n2. ตั้งชื่อเสียง แล้วเลือกจาก dropdown\n3. กดสร้างคลิป — ระบบจะ:\n   • สร้างเสียง TTS ปกติก่อน\n   • แปลงน้ำเสียงให้เหมือนเสียงต้นแบบ\n\n<b>ไม่ใช้</b> = ใช้เสียง edge-tts ปกติ (เปรมวดี/นิวัตน์)"
  },
  persona: {
    title: "บุคลิกตัวละคร",
    body: "กำหนดบุคลิกของผู้พูดในคลิป เพื่อให้ AI สร้างสคริปต์ตามสไตล์ที่ต้องการ\n\n<b>ตัวอย่าง:</b>\n• พี่โค้ด โปรแกรมเมอร์สายฮา พูดจาเป็นกันเอง\n• ครูสอนเทค พูดช้าๆ อธิบายละเอียด\n• นักข่าว IT รายงานข่าวเทคโนโลยี\n\nถ้าปล่อยว่าง = AI ใช้สไตล์มาตรฐาน"
  },
  script: {
    title: "สคริปต์กำหนดเอง",
    body: "เขียนสคริปต์เองแทนการให้ AI สร้าง\n\n<b>โหมดบรรยาย:</b> เขียนเนื้อหาตรงๆ หรือใส่แท็ก:\n[Hook 3 วินาที] — ประโยคเปิด\n[ปัญหา 10 วินาที] — ...\n\n<b>โหมดสนทนา:</b> ใช้รูปแบบ:\nB: คำถาม\nA: คำตอบ\n\n<b>ตัวนับด้านล่าง</b> ประมาณความยาว (~8 ตัวอักษร/วินาที)\nสีเหลือง = ใกล้ 60 วิ, สีแดง = เกิน 60 วิ\n\nถ้าปล่อยว่าง = AI จะสร้างสคริปต์ให้อัตโนมัติ"
  },
};

function showHelp(key) {
  const h = HELP_TEXTS[key];
  if (!h) return;
  document.getElementById("helpTitle").textContent = h.title;
  document.getElementById("helpBody").innerHTML = h.body.replace(/\n/g, "<br>");
  document.getElementById("helpModal").classList.remove("hidden");
}

function closeHelp() {
  document.getElementById("helpModal").classList.add("hidden");
}

document.getElementById("topicInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") startGenerate();
});

loadHistory();
loadVoiceProfiles();
