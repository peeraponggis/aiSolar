let currentProjectId = null;
let pollTimer = null;
let selectedVoice = "female";
let subtitlesEnabled = true;
let selectedMedia = [];
let cloneVoiceId = "";
let selectedMode = "narration";
let selectedVoiceB = "male";
let selectedTone = "cheerful";
let selectedAspectRatios = ["9:16"];
let selectedDuration = "short";
let selectedCloneEngine = "openvoice";
let bgmFilename = "";
let consoleExpanded = false;
let logLastTimestamp = 0;
let generateStartTime = null;
let _pollingLogs = false;
let unseenLogCount = 0;

const PHASE_LABELS = {
  pending: "รอเริ่ม...",
  brainstorming: "กำลังระดมสมอง + เขียนสคริปต์...",
  script_done: "ได้สคริปต์แล้ว",
  generating_audio: "กำลังสร้างเสียง...",
  audio_done: "ได้เสียงแล้ว",
  creating_video: "กำลังเตรียมสื่อ / สร้างวิดีโอ...",
  media_ready: "พร้อมแล้ว — ตรวจ Storyboard แล้วกดสร้างวิดีโอ",
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

async function loadCloneEngines() {
  try {
    const resp = await fetch("/api/clone-engines");
    if (!resp.ok) return;
    const engines = await resp.json();
    const sel = document.getElementById("cloneEngineSelect");
    sel.innerHTML = "";
    for (const eng of engines) {
      const opt = document.createElement("option");
      opt.value = eng.name;
      opt.textContent = eng.label + (eng.available ? "" : " (ไม่ได้ติดตั้ง)");
      opt.disabled = !eng.available;
      sel.appendChild(opt);
    }
    sel.value = selectedCloneEngine;
  } catch {}
}

function onCloneEngineChange(engineName) {
  selectedCloneEngine = engineName;
  _updateCloneDependentRows();
}

// F5 speaks straight from the reference voice, so base-TTS rate/pitch don't apply.
function _updateCloneDependentRows() {
  const f5 = Boolean(cloneVoiceId) && selectedCloneEngine === "f5-tts-thai";
  document.getElementById("rateRow").classList.toggle("hidden", f5);
  document.getElementById("pitchRow").classList.toggle("hidden", f5);
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

const TONE_PERSONAS = {
  normal:    "ผู้บรรยายทั่วไป พูดชัดเจน น้ำเสียงราบเรียบ เป็นกลาง ให้ข้อมูลตรงไปตรงมา",
  cheerful:  "คนสนุกสนาน ร่าเริง พูดจามีชีวิตชีวา ชอบใช้คำอุทาน เช่น 'เจ๋งมาก!' 'สุดยอดเลย!' ทำให้ผู้ฟังรู้สึกสนุกตาม",
  energetic: "คนกระตือรือร้น ตื่นเต้นกับทุกเรื่อง พูดเร็ว มีพลัง ชอบย้ำว่า 'ต้องลอง!' 'พลาดไม่ได้!' สร้างความรู้สึกเร่งด่วน",
  warm:      "พี่คนสนิท พูดจาอบอุ่น เป็นกันเอง ใช้คำว่า 'นะ' 'จ้า' 'เนอะ' ทำให้รู้สึกเหมือนคุยกับเพื่อน",
  serious:   "ผู้เชี่ยวชาญมืออาชีพ พูดจริงจัง ใช้ข้อมูลสนับสนุน น่าเชื่อถือ หนักแน่น ไม่ใช้คำสแลง",
  news:      "ผู้ประกาศข่าว รายงานข้อมูลชัดเจน กระชับ เป็นทางการ ใช้ภาษาสุภาพ มีการสรุปประเด็นสำคัญ",
};

function selectTone(value) {
  selectedTone = value;
  const customRow = document.getElementById("customToneRow");
  if (value === "custom") {
    customRow.classList.remove("hidden");
  } else {
    customRow.classList.add("hidden");
  }
  const personaInput = document.getElementById("personaInput");
  if (TONE_PERSONAS[value] && !personaInput._userEdited) {
    personaInput.value = TONE_PERSONAS[value];
  }
}

function onPersonaInput() {
  const el = document.getElementById("personaInput");
  el._userEdited = el.value.trim() !== "" && !Object.values(TONE_PERSONAS).includes(el.value.trim());
}

// Set default persona from initial tone
if (TONE_PERSONAS[selectedTone]) {
  document.getElementById("personaInput").value = TONE_PERSONAS[selectedTone];
}

const DURATION_THRESHOLDS = {
  short:  { warn: 50, over: 60 },
  medium: { warn: 120, over: 180 },
  long:   { warn: 180, over: 300 },
};

function selectDuration(preset) {
  selectedDuration = preset;
  document.querySelectorAll("[data-dur]").forEach(b => {
    b.classList.toggle("active", b.dataset.dur === preset);
  });
  updateScriptCounter();
}

function updateTauLabel() {
  const v = parseInt(document.getElementById("tauSlider").value);
  document.getElementById("tauLabel").textContent = (v / 100).toFixed(2);
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

// ── Script counter ──

function updateScriptCounter() {
  const el = document.getElementById("scriptCounter");
  const text = document.getElementById("customScriptInput").value.trim();
  if (!text) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  const cleaned = text.replace(/\[.*?\]/g, "").replace(/[—\-–]+/g, " ").trim();
  const chars = cleaned.length;
  const thaiRate = 8;
  const estSec = Math.round(chars / thaiRate);
  const th = DURATION_THRESHOLDS[selectedDuration] || DURATION_THRESHOLDS.short;
  el.className = "script-counter" + (estSec > th.over ? " over" : estSec > th.warn ? " warn" : "");
  const icon = estSec > th.over ? "!!" : estSec > th.warn ? "!" : "";
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
  const scrape = document.getElementById("scrapeResults");
  if (scrape) scrape.classList.toggle("ratio-landscape", isLandscape);
}

function switchVideoRatio(projectId, ratio, btn) {
  document.getElementById("videoPlayer").src =
    `/api/download/${projectId}?ratio=${encodeURIComponent(ratio)}`;
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
      _scheduleSaveForm();
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
  _scheduleSaveForm();
  document.getElementById("bgmEmpty").classList.remove("hidden");
  document.getElementById("bgmPreview").classList.add("hidden");
  document.getElementById("bgmPlayer").src = "";
}

// ── Media management ──

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

async function scrapeUrl() {
  const url = document.getElementById("scrapeUrl").value.trim();
  if (!url) return;
  const grid = document.getElementById("scrapeResults");
  grid.innerHTML = '<p class="loading">กำลังดึงรูปจากเว็บ...</p>';
  try {
    const resp = await fetch(`/api/url/scrape?url=${encodeURIComponent(url)}`);
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      grid.innerHTML = `<p class="no-results">${err.error || "ไม่สามารถดึงรูปได้"}</p>`;
      return;
    }
    const items = await resp.json();
    if (!items.length) {
      grid.innerHTML = '<p class="no-results">ไม่พบรูปภาพ/วิดีโอในหน้านี้</p>';
      return;
    }
    grid.innerHTML = items
      .map(
        (item, i) => `
      <div class="pexels-item" onclick="addScrapedMedia(${i})" data-scrape-index="${i}">
        <img src="/api/url/proxy?url=${encodeURIComponent(item.thumbnail)}" alt="" loading="lazy" onerror="this.parentElement.style.display='none'">
        <span class="pexels-badge">${item.type === "video" ? "VID" : "IMG"}</span>
      </div>`
      )
      .join("");
    window._scrapeResults = items;
    document.getElementById("clearScrapeBtn").classList.remove("hidden");
    updateMediaAspectRatio();
  } catch (e) {
    grid.innerHTML = '<p class="no-results">ดึงรูปไม่สำเร็จ</p>';
  }
}

function clearScrape() {
  document.getElementById("scrapeResults").innerHTML = "";
  document.getElementById("scrapeUrl").value = "";
  document.getElementById("clearScrapeBtn").classList.add("hidden");
  window._scrapeResults = null;
}

async function addScrapedMedia(index) {
  const items = window._scrapeResults;
  if (!items || !items[index]) return;
  const item = items[index];
  const el = document.querySelector(`.pexels-item[data-scrape-index="${index}"]`);
  if (el) el.classList.add("downloading");
  try {
    const resp = await fetch(
      `/api/url/download?url=${encodeURIComponent(item.url)}&media_type=${item.type}`,
      { method: "POST" }
    );
    const data = await resp.json();
    if (data.ok) {
      selectedMedia.push({
        filename: data.filename,
        type: data.type,
        thumbnail: `/api/uploads/file/${data.filename}`,
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
  _scheduleSaveForm();
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
      <div class="media-duration-input">
        <input type="number" min="0" step="0.5" placeholder="auto"
          value="${m.displayDuration || ""}"
          onchange="setMediaDuration(${i}, this.value)"
          onclick="event.stopPropagation()" title="ความยาว (วินาที)">
        <span>s</span>
      </div>
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

function setMediaDuration(index, value) {
  const dur = parseFloat(value);
  selectedMedia[index].displayDuration = dur > 0 ? dur : 0;
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

// ── Script normalisation (pure Thai, readings, numbers, scene paragraphs) ──

let _scriptBeforeNormalize = null;
const SCENES_PER_PRESET = { short: 4, medium: 8, long: 12 };

async function normalizeScript() {
  const input = document.getElementById("customScriptInput");
  const text = input.value.trim();
  if (!text) return showToast("วางข้อความในช่องสคริปต์ก่อน", true);
  const scenes = selectedMedia.length || SCENES_PER_PRESET[selectedDuration] || 4;
  const btn = document.getElementById("normalizeScriptBtn");
  btn.disabled = true;
  btn.textContent = "กำลังแปลง... (อาจใช้เวลา 1 นาที)";
  try {
    const resp = await fetch("/api/script/normalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, scenes }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "แปลงไม่สำเร็จ");
    _scriptBeforeNormalize = input.value;
    input.value = data.text;
    updateScriptCounter();
    document.getElementById("undoScriptBtn").classList.remove("hidden");
    showToast(`แบ่งเป็น ${data.paragraphs} ฉาก — ตรวจข้อความก่อนสร้างคลิป`);
    const guessed = Object.entries(data.guessed || {});
    const notes = [...(data.warnings || [])];
    if (guessed.length) {
      notes.unshift("คำอ่านที่ระบบเดา (เพิ่มในคำอ่านภาษาอังกฤษได้ถ้าถูก): " +
        guessed.slice(0, 6).map(([en, th]) => `${en} → ${th}`).join(", "));
    }
    notes.forEach((n, i) => setTimeout(() => showToast(n, !n.startsWith("คำอ่านที่ระบบเดา")), 3200 * (i + 1)));
  } catch (e) {
    showToast(e.message || "แปลงไม่สำเร็จ", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ แปลงสคริปต์";
  }
}

function undoNormalizeScript() {
  if (_scriptBeforeNormalize === null) return;
  document.getElementById("customScriptInput").value = _scriptBeforeNormalize;
  _scriptBeforeNormalize = null;
  updateScriptCounter();
  document.getElementById("undoScriptBtn").classList.add("hidden");
}

// ── Voice Preview ──

async function previewVoice() {
  const scriptInput = document.getElementById("customScriptInput");
  const selStart = scriptInput.selectionStart;
  const selEnd = scriptInput.selectionEnd;
  const selected = selEnd > selStart
    ? scriptInput.value.substring(selStart, selEnd).trim()
    : "";
  const text = selected || scriptInput.value.trim();
  if (!text) return showToast("กรุณาใส่สคริปต์ก่อนทดสอบเสียง", true);
  if (selected) {
    showToast(`ทดสอบเฉพาะส่วนที่ไฮไลท์ (${selected.length} ตัวอักษร)`);
  }
  const btn = document.getElementById("previewVoiceBtn");
  btn.disabled = true;
  btn.textContent = "กำลังสร้างเสียง...";
  try {
    const params = new URLSearchParams({
      text,
      voice: selectedVoice,
      rate: getRateValue(),
      pitch: getPitchValue(),
      tone: selectedTone,
    });
    if (selectedTone === "custom") {
      params.set("tone_rate", document.getElementById("customToneRate").value || "0");
      params.set("tone_pitch", document.getElementById("customTonePitch").value || "0");
    }
    if (cloneVoiceId) {
      params.set("clone_voice_id", cloneVoiceId);
      params.set("clone_tau", document.getElementById("tauSlider")?.value || "30");
      params.set("clone_engine", selectedCloneEngine);
    }
    const resp = await fetch(`/api/preview-voice?${params}`, { method: "POST" });
    if (!resp.ok) throw new Error();
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const player = document.getElementById("voicePreviewPlayer");
    player.src = url;
    player.classList.remove("hidden");
    player.play();
  } catch {
    showToast("ทดสอบเสียงไม่สำเร็จ", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "ทดสอบเสียง";
  }
}

// ── Replacements Editor ──

let _replacements = {};

async function openReplacements() {
  try {
    const resp = await fetch("/api/replacements");
    _replacements = await resp.json();
  } catch { _replacements = {}; }
  renderReplacements();
  document.getElementById("replacementsModal").classList.remove("hidden");
}

function closeReplacements() {
  document.getElementById("replacementsModal").classList.add("hidden");
}

function renderReplacements(filter = "") {
  const el = document.getElementById("replacementsList");
  const q = filter.trim().toLowerCase();
  let entries = Object.entries(_replacements);
  if (q) {
    entries = entries.filter(([eng, thai]) =>
      eng.toLowerCase().includes(q) || thai.toLowerCase().includes(q)
    );
  }
  const sorted = entries.sort((a, b) => a[0].localeCompare(b[0]));
  el.innerHTML = sorted.length
    ? sorted.map(([eng, thai]) => `<div class="repl-item" data-key="${_escapeAttr(eng)}">
        <div class="repl-view">${escapeHtml(eng)} <span>&rarr;</span> ${escapeHtml(thai)}</div>
        <div class="repl-actions">
          <button class="repl-edit" onclick="startEditReplacement('${eng.replace(/'/g, "\\'")}')" title="แก้ไข">&#9998;</button>
          <button class="repl-remove" onclick="removeReplacement('${eng.replace(/'/g, "\\'")}')" title="ลบ">&times;</button>
        </div>
      </div>`).join("")
    : `<p class="no-results">ไม่พบคำที่ตรงกับ "${escapeHtml(filter.trim())}"</p>`;
}

function startEditReplacement(key) {
  const row = document.querySelector(`.repl-item[data-key="${CSS.escape(key)}"]`);
  if (!row) return;
  const thai = _replacements[key] || "";
  row.innerHTML = `
    <div class="repl-edit-row">
      <input type="text" class="repl-edit-eng" value="${_escapeAttr(key)}" onkeydown="if(event.key==='Enter')this.closest('.repl-item').querySelector('.repl-save').click(); if(event.key==='Escape')renderReplacements(document.getElementById('replEng').value);">
      <span>&rarr;</span>
      <input type="text" class="repl-edit-thai" value="${_escapeAttr(thai)}" onkeydown="if(event.key==='Enter')this.closest('.repl-item').querySelector('.repl-save').click(); if(event.key==='Escape')renderReplacements(document.getElementById('replEng').value);">
    </div>
    <div class="repl-actions">
      <button class="repl-save" onclick="confirmEditReplacement('${key.replace(/'/g, "\\'")}', this)" title="บันทึก">&#10003;</button>
      <button class="repl-remove" onclick="renderReplacements(document.getElementById('replEng').value)" title="ยกเลิก">&times;</button>
    </div>`;
  row.querySelector(".repl-edit-eng").focus();
}

function confirmEditReplacement(oldKey, btn) {
  const row = btn.closest(".repl-item");
  const newEng = row.querySelector(".repl-edit-eng").value.trim();
  const newThai = row.querySelector(".repl-edit-thai").value.trim();
  if (!newEng || !newThai) return showToast("กรุณากรอกทั้งคำอังกฤษและคำอ่านไทย", true);
  if (newEng !== oldKey) delete _replacements[oldKey];
  _replacements[newEng] = newThai;
  renderReplacements(document.getElementById("replEng").value);
}

function exportReplacementsTxt() {
  const sorted = Object.entries(_replacements).sort((a, b) => a[0].localeCompare(b[0]));
  if (!sorted.length) return showToast("ไม่มีคำแทนให้ส่งออก", true);
  const lines = sorted.map(([eng, thai]) => `${eng} -> ${thai}`).join("\n");
  const blob = new Blob([lines], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "replacements.txt";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  showToast(`ส่งออก ${sorted.length} คำแล้ว`);
}

function checkDuplicateReplacement() {
  const eng = document.getElementById("replEng").value.trim();
  const warn = document.getElementById("replDupWarn");
  renderReplacements(eng);
  if (!eng) { warn.classList.add("hidden"); return; }
  const key = Object.keys(_replacements).find(k => k.toLowerCase() === eng.toLowerCase());
  if (key) {
    warn.textContent = `"${key}" มีอยู่แล้ว → ${_replacements[key]}`;
    warn.classList.remove("hidden");
  } else {
    warn.classList.add("hidden");
  }
}

function addReplacement() {
  const eng = document.getElementById("replEng").value.trim();
  const thai = document.getElementById("replThai").value.trim();
  if (!eng || !thai) return showToast("กรุณากรอกทั้งคำอังกฤษและคำอ่านไทย", true);
  _replacements[eng] = thai;
  document.getElementById("replEng").value = "";
  document.getElementById("replThai").value = "";
  renderReplacements();
}

function removeReplacement(eng) {
  delete _replacements[eng];
  renderReplacements(document.getElementById("replEng").value);
}

async function saveReplacements() {
  try {
    const resp = await fetch("/api/replacements", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(_replacements),
    });
    if (!resp.ok) throw new Error();
    showToast("บันทึกคำแทนสำเร็จ");
    closeReplacements();
  } catch {
    showToast("บันทึกไม่สำเร็จ", true);
  }
}

// ── Generate ──

// Everything the server needs to make a clip, from the current settings.
function _generateSettings(topic) {
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
    duration_preset: selectedDuration,
    clone_tau: document.getElementById("tauSlider").value,
    tone_var: selectedTone === "custom" ? (document.getElementById("customToneVar").value || 10) : 0,
    tone_rate: selectedTone === "custom" ? (document.getElementById("customToneRate").value || 0) : 0,
    tone_pitch: selectedTone === "custom" ? (document.getElementById("customTonePitch").value || 0) : 0,
    overlay_text: (document.getElementById("overlayTextInput").value || "").trim(),
    overlay_font: document.getElementById("overlayFont").value,
    overlay_animation: document.getElementById("overlayAnimation").value,
    clone_engine: selectedCloneEngine,
    run_mode: selectedRunMode,
    media_source: selectedMediaSource,
    ai_engine: selectedAiEngine,
    graphics: selectedGraphics,
  });
  if (selectedMedia.length) {
    params.set("media_files", selectedMedia.map((m) => m.filename).join(","));
    const durations = selectedMedia.map((m) => m.displayDuration || 0);
    if (durations.some((d) => d > 0)) {
      params.set("media_durations", durations.join(","));
    }
  }
  if (videoTemplateFields) {
    params.set("template_fields", JSON.stringify(videoTemplateFields));
  }

  return Object.fromEntries(params);
}

async function startGenerate() {
  const input = document.getElementById("topicInput");
  const topic = input.value.trim();
  if (!topic) return showToast("กรุณาใส่หัวข้อ", true);

  const btn = document.getElementById("generateBtn");
  btn.disabled = true;
  btn.textContent = "กำลังสร้าง...";

  // The previous clip stays visible (dimmed) until the new one is ready.
  document.getElementById("resultSection").classList.add("stale");
  _showWorkSection("progressSection", `กำลังสร้าง: ${topic}`);
  updateProgress(0, "pending");

  generateStartTime = Date.now();
  logLastTimestamp = 0;
  unseenLogCount = 0;
  document.getElementById("consoleLogs").innerHTML = "";
  updateConsoleBadge();
  document.getElementById("etaText").textContent = "";

  const settings = _generateSettings(topic);

  try {
    const resp = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(settings),
    });
    const data = await resp.json();
    if (!resp.ok) {
      const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail || data.error;
      showToast(`สร้างคลิปไม่ได้: ${detail || resp.status}`, true);
      resetButton();
      return;
    }
    currentProjectId = data.id;
    _rememberProject(currentProjectId);
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

      if (data.phase === "media_ready") {
        clearInterval(pollTimer);
        pollTimer = null;
        setTimeout(pollLogs, 500);
        updateEta(0);
        showStoryboardPreview(data);
        resetButton();
        loadHistory();
        showToast("ตรวจ Storyboard แล้วกด สร้างวิดีโอ");
      } else if (data.phase === "done") {
        clearInterval(pollTimer);
        pollTimer = null;
        setTimeout(pollLogs, 500);
        updateEta(100);
        showResult(data);
        resetButton();
        showToast("สร้างคลิปเสร็จแล้ว ค่ะ");
        playDoneSound();
        loadHistory();
      } else if (data.phase === "error") {
        clearInterval(pollTimer);
        pollTimer = null;
        setTimeout(pollLogs, 500);
        updateEta(0);
        showToast((data.error || "เกิดข้อผิดพลาด").split("\n").filter(Boolean).pop(), true);
        resetButton();
        loadHistory();
        if (data.render_params && data.audio_path) showStoryboardPreview(data);
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

// Bring a right-hand panel into view (matters in the one-column layout,
// where it sits below all the settings).
function _showWorkSection(id, title) {
  document.getElementById("emptyState").classList.add("hidden");
  const el = document.getElementById(id);
  el.classList.remove("hidden");
  if (title) document.getElementById("progressTitle").textContent = title;
  const top = el.getBoundingClientRect().top;
  if (top < 0 || top > window.innerHeight * 0.6) {
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function _fillCommonResult(data) {
  const section = document.getElementById("resultSection");
  section.classList.remove("stale");
  document.getElementById("progressSection").classList.remove("hidden");
  document.getElementById("progressTitle").textContent = data.topic || "สถานะ";
  updateProgress(data.progress, data.phase);

  document.getElementById("scriptContent").textContent = data.script || "";
  document.getElementById("audioPlayer").src = data.audio_path ? `/api/audio/${data.project_id}` : "";

  const vsInfoEl = document.getElementById("voiceSettingsInfo");
  const vs = data.voice_settings;
  if (vs) {
    let label = vs.clone_name ? `${vs.clone_name} (${vs.clone_engine})` : `${vs.voice} (edge-tts)`;
    if (vs.tone && vs.tone !== "normal") label += ` | ${vs.tone}`;
    vsInfoEl.textContent = label;
  }
  vsInfoEl.classList.toggle("hidden", !vs);
  _renderReviewBox(data);
  _renderPostInfo(data);
}

function showResult(data) {
  _fillCommonResult(data);
  document.querySelector('.tab[data-tab="video"]').classList.remove("hidden");

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
    document.getElementById("videoPlayer").src =
      `/api/download/${data.project_id}?ratio=${encodeURIComponent(firstRatio)}&t=${data.updated_at || ""}`;

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

  _sbPhase = "done";
  buildStoryboard(data);
  switchTab("video");
  _showWorkSection("resultSection");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.toggle("active", c.id === `tab-${name}`));
}

function newClip() {
  document.getElementById("topicInput").value = "";
  document.getElementById("customScriptInput").value = "";
  updateScriptCounter();
  if (selectedMedia.length) clearAllMedia();
  currentProjectId = null;
  try { sessionStorage.removeItem(PROJECT_KEY); } catch { /* storage unavailable */ }
  _scheduleSaveForm();
  document.getElementById("setupPanel").scrollTo({ top: 0, behavior: "smooth" });
  window.scrollTo({ top: 0, behavior: "smooth" });
  document.getElementById("topicInput").focus();
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

function playDoneSound() {
  try {
    const audio = new Audio("/static/sounds/clip_done.mp3");
    audio.volume = 0.4;
    audio.play().catch(() => {});
  } catch {}
}

// ── Storyboard ──

let _sbProjectId = null;
let _sbScenes = [];
let _sbMediaFiles = [];
let _sbDurations = [];
let _sbRemoved = [];
let _sbQueries = [];
let _sbPhase = null;
let _sbDragIdx = null;

function showStoryboardPreview(data) {
  currentProjectId = data.project_id;
  _rememberProject(currentProjectId);
  _fillCommonResult(data);
  // No finished video yet: the Video tab would be empty.
  document.querySelector('.tab[data-tab="video"]').classList.add("hidden");
  _sbPhase = "media_ready";
  switchTab("storyboard");
  buildStoryboard(data);
  _showWorkSection("resultSection");
}

// What the storyboard currently shows; the preview and the real render use the same.
function _storyboardBody() {
  const body = {};
  const scriptText = _sbScenes.filter((s) => s.trim()).join("\n\n");
  if (scriptText) body.script = scriptText;
  // Rows can be text-only after dragging; keep order and durations paired.
  const order = [], durations = [];
  _sbMediaFiles.forEach((m, i) => {
    if (!m) return;
    order.push(m.filename);
    durations.push(_sbDurations[i] || 0);
  });
  body.media_order = order;
  body.media_durations = durations.some((d) => d > 0) ? durations : null;
  return body;
}

// ── Quick preview ──

let _previewTimer = null;

function _resetPreview() {
  if (_previewTimer) { clearInterval(_previewTimer); _previewTimer = null; }
  const v = document.getElementById("sbPreviewVideo");
  v.pause(); v.removeAttribute("src"); v.load();
  document.getElementById("sbPreview").classList.add("hidden");
}

function _markPreviewOutdated() {
  if (document.getElementById("sbPreview").classList.contains("hidden")) return;
  const note = document.getElementById("sbPreviewNote");
  note.textContent = "⚠ แก้ Storyboard หลังทำตัวอย่าง — กดดูตัวอย่างอีกครั้ง";
  note.classList.add("outdated");
}

async function _startPreview() {
  if (!currentProjectId) return;
  const pid = currentProjectId;
  const btn = document.querySelector(".sb-preview-btn");
  btn.disabled = true;
  const started = Date.now();
  btn.textContent = "กำลังทำตัวอย่าง...";
  try {
    const resp = await fetch(`/api/project/${pid}/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(_storyboardBody()),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "เริ่มทำตัวอย่างไม่ได้");
  } catch (e) {
    showToast(e.message, true);
    btn.disabled = false;
    btn.textContent = "👁 ดูตัวอย่างเร็ว";
    return;
  }
  if (_previewTimer) clearInterval(_previewTimer);
  _previewTimer = setInterval(async () => {
    const b = document.querySelector(".sb-preview-btn");
    if (b) b.textContent = `กำลังทำตัวอย่าง... ${Math.round((Date.now() - started) / 1000)} วิ`;
    let st;
    try { st = await (await fetch(`/api/project/${pid}/preview/status`)).json(); } catch { return; }
    if (st.status === "running") return;
    clearInterval(_previewTimer);
    _previewTimer = null;
    if (b) { b.disabled = false; b.textContent = "👁 ดูตัวอย่างเร็ว"; }
    if (pid !== currentProjectId) return;
    if (st.status !== "done") return showToast(st.error || "ทำตัวอย่างไม่สำเร็จ", true);
    const box = document.getElementById("sbPreview");
    const video = document.getElementById("sbPreviewVideo");
    video.classList.toggle("landscape", st.ratio === "16:9");
    video.src = `/api/project/${pid}/preview/video?t=${Date.now()}`;
    const note = document.getElementById("sbPreviewNote");
    note.textContent = `ทำเสร็จใน ${st.seconds} วิ`;
    note.classList.remove("outdated");
    box.classList.remove("hidden");
    box.scrollIntoView({ behavior: "smooth", block: "start" });
    video.play().catch(() => {});
  }, 1000);
}

async function _startRender() {
  if (!currentProjectId) return;
  const btn = document.querySelector(".sb-render-btn");
  if (btn) { btn.disabled = true; btn.textContent = "กำลังสร้าง..."; }
  _sbPhase = "rendering";
  _resetPreview();
  const body = _storyboardBody();

  try {
    const resp = await fetch(`/api/project/${currentProjectId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error("render start failed");
    generateStartTime = Date.now();
    _showWorkSection("progressSection");
    pollStatus();
  } catch (e) {
    showToast("เริ่มสร้างวิดีโอไม่ได้", true);
    if (btn) { btn.disabled = false; btn.textContent = "สร้างวิดีโอ"; }
    _sbPhase = "media_ready";
  }
}

async function buildStoryboard(data) {
  const container = document.getElementById("storyboardTimeline");
  if (!data.script || !data.project_id) {
    container.innerHTML = '<p class="no-results">ไม่มีข้อมูล storyboard</p>';
    return;
  }

  if (_sbProjectId !== data.project_id) _resetPreview();
  _sbProjectId = data.project_id;
  _sbScenes = data.script
    .split(/\n\s*\n/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  try {
    const resp = await fetch(`/api/project/${data.project_id}/media`);
    if (resp.ok) _sbMediaFiles = await resp.json();
  } catch {}
  await _loadSceneInfo(data.project_id);
  _sbQueries = _sbScenes.map((_, i) => _sceneQuery(i));

  const n = Math.max(_sbScenes.length, _sbMediaFiles.length);
  _sbDurations = new Array(n).fill(0);
  _sbRemoved = [];

  _renderStoryboard();
}

function _sbMismatchWarning() {
  const nScenes = _sbScenes.filter((s) => s && s.trim()).length;
  const nMedia = _sbMediaFiles.filter(Boolean).length;
  if (nScenes === nMedia) return "";

  let msg;
  if (nMedia > nScenes) {
    const extra = nMedia - nScenes;
    msg = `มีสื่อ ${nMedia} ชิ้น แต่สคริปต์มี ${nScenes} ซีน — สื่อ ${extra} ชิ้นท้ายจะไม่มีคำบรรยาย เพิ่มข้อความในซีนท้าย หรือลบสื่อที่เกินออก`;
  } else {
    const missing = nScenes - nMedia;
    msg = `มีสคริปต์ ${nScenes} ซีน แต่สื่อมี ${nMedia} ชิ้น — ขาดสื่ออีก ${missing} ชิ้น ซีนท้ายจะใช้สื่อซ้ำ`;
  }
  return `<div class="sb-warning"><span>⚠</span><span>${escapeHtml(msg)}</span></div>`;
}

function _renderStoryboard() {
  const container = document.getElementById("storyboardTimeline");
  const pid = _sbProjectId;
  let html = "";
  const editable = _sbPhase === "media_ready";

  if (editable) {
    html += _sbMismatchWarning();
    html += `<div class="sb-render-bar">
      <span>ลากที่ ≡ เพื่อสลับลำดับ · คลิกรูปเพื่อเปลี่ยนสื่อ · แก้ข้อความเปลี่ยนเฉพาะซับไตเติ้ล (ไม่เปลี่ยนเสียง)</span>
      <button class="tool-btn sb-preview-btn" onclick="_startPreview()">👁 ดูตัวอย่างเร็ว</button>
      <button class="btn primary sb-render-btn" onclick="_startRender()">สร้างวิดีโอ</button>
    </div>`;
  }

  html += '<div class="sb-scenes">';
  const maxScenes = Math.max(_sbScenes.length, _sbMediaFiles.length);
  for (let i = 0; i < maxScenes; i++) {
    const media = _sbMediaFiles[i];
    const text = _sbScenes[i] || "";
    const sceneNum = i + 1;
    const fname = media ? _escapeAttr(media.filename) : "";

    let thumbContent;
    if (media) {
      const src = `/api/project/${pid}/media/${media.filename}`;
      if (media.type === "video") {
        thumbContent = `<video src="${src}" preload="metadata" muted></video>`;
      } else {
        thumbContent = `<img src="${src}" alt="Scene ${sceneNum}" loading="lazy">`;
      }
    } else {
      thumbContent = '<div class="sb-no-media">ไม่มีสื่อ</div>';
    }

    let bodyHtml;
    if (editable) {
      const dur = _sbDurations[i] || 0;
      bodyHtml = `<textarea class="sb-script-edit" rows="2"
          placeholder="(ไม่มีข้อความ — สื่อนี้จะแสดงโดยไม่มีซับไตเติ้ล)"
          oninput="_sbEditScript(${i},this.value)">${escapeHtml(text)}</textarea>
        <div class="sb-duration-row">
          <span>เวลา</span>
          <input type="number" class="sb-duration-input" min="0" max="60" step="0.5"
            value="${dur || ""}" placeholder="auto"
            oninput="_sbEditDuration(${i},this.value)">
          <span>วินาที${dur ? "" : " (อัตโนมัติ)"}</span>
        </div>`;
    } else {
      const truncated = text.length > 120 ? text.substring(0, 120) + "…" : text;
      bodyHtml = text
        ? `<div class="sb-text">${escapeHtml(truncated)}</div>`
        : '<div class="sb-extra-label">(ไม่มีข้อความ)</div>';
    }

    const dragAttrs = editable
      ? `draggable="true" ondragstart="_sbDragStart(event,${i})" ondragover="_sbDragOver(event,${i})" ondrop="_sbDrop(event,${i})" ondragend="_sbDragEnd(event)"`
      : "";

    html += `<div class="sb-scene" ${dragAttrs}>
      ${editable ? '<div class="sb-drag-handle" title="ลากเพื่อสลับลำดับ">≡</div>' : ""}
      <div class="sb-scene-num">${sceneNum}</div>
      <div class="sb-thumb" onclick="openMediaPicker(${i},'${fname}')" title="${media ? "คลิกเพื่อเปลี่ยนสื่อ" : "คลิกเพื่อเลือกสื่อ"}">${thumbContent}</div>
      <div class="sb-body">${bodyHtml}${_sbQueries[i] ? `<div class="sb-query" title="คำค้นภาพของฉากนี้">🔎 ${escapeHtml(_sbQueries[i])}</div>` : ""}</div>
      ${editable && _aiImagesAvailable ? `<button class="sb-ai" title="สร้างภาพ AI ให้ฉากนี้" onclick="_sbAiImage(${i})">🎨</button>` : ""}
      ${editable && _graphicsAvailable ? `<button class="sb-card" title="สร้างการ์ดตัวเลขให้ฉากนี้" onclick="openCardDialog(${i})">📊</button>` : ""}
      ${editable && media ? `<button class="sb-remove" title="เอาสื่อนี้ออกจากวิดีโอ (เลือกกลับมาได้)" onclick="_sbRemoveMedia(${i})">🗑</button>` : ""}
    </div>`;
  }
  html += "</div>";

  container.innerHTML = html;
}

function _sbEditScript(idx, text) {
  while (_sbScenes.length <= idx) _sbScenes.push("");
  _sbScenes[idx] = text;
  _markPreviewOutdated();
}

function _sbEditDuration(idx, val) {
  while (_sbDurations.length <= idx) _sbDurations.push(0);
  _sbDurations[idx] = parseFloat(val) || 0;
  _markPreviewOutdated();
}

function _sbClearDropMarks() {
  document.querySelectorAll(".sb-scene").forEach((el) => {
    el.classList.remove("sb-drop-above", "sb-drop-below", "sb-dragging");
  });
}

function _sbDragStart(e, idx) {
  _sbDragIdx = idx;
  e.dataTransfer.effectAllowed = "move";
  e.dataTransfer.setData("text/plain", String(idx));
  e.currentTarget.classList.add("sb-dragging");
}

function _sbDragOver(e, idx) {
  if (_sbDragIdx === null || _sbDragIdx === idx) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = "move";
  document.querySelectorAll(".sb-scene").forEach((el) => {
    el.classList.remove("sb-drop-above", "sb-drop-below");
  });
  e.currentTarget.classList.add(idx < _sbDragIdx ? "sb-drop-above" : "sb-drop-below");
}

function _sbDrop(e, targetIdx) {
  e.preventDefault();
  const src = _sbDragIdx;
  _sbDragIdx = null;
  _sbClearDropMarks();
  if (src === null || src === targetIdx) return;

  const n = Math.max(_sbScenes.length, _sbMediaFiles.length, src + 1, targetIdx + 1);
  while (_sbScenes.length < n) _sbScenes.push("");
  while (_sbDurations.length < n) _sbDurations.push(0);

  const move = (arr) => {
    const [item] = arr.splice(src, 1);
    arr.splice(targetIdx, 0, item);
  };
  move(_sbMediaFiles);
  move(_sbScenes);
  move(_sbDurations);
  while (_sbQueries.length < n) _sbQueries.push("");
  move(_sbQueries);

  _markPreviewOutdated();
  _renderStoryboard();
}

function _sbDragEnd() {
  _sbDragIdx = null;
  _sbClearDropMarks();
}

function openMediaPicker(sceneIdx, currentFilename) {
  let existing = document.getElementById("sbPickerOverlay");
  if (existing) existing.remove();

  const overlay = document.createElement("div");
  overlay.id = "sbPickerOverlay";
  overlay.className = "sb-picker-overlay";
  overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

  let grid = "";
  const choices = [..._sbMediaFiles.filter(Boolean), ..._sbRemoved.map((m) => ({ ...m, removed: true }))];
  for (const m of choices) {
    const src = `/api/project/${_sbProjectId}/media/${m.filename}`;
    const active = m.filename === currentFilename ? " sb-pick-active" : "";
    const tag = m.type === "video"
      ? `<video src="${src}" preload="metadata" muted></video>`
      : `<img src="${src}" loading="lazy">`;
    const label = m.removed ? `${escapeHtml(m.filename)} (เอาออกแล้ว)` : escapeHtml(m.filename);
    grid += `<div class="sb-pick-item${active}${m.removed ? " sb-pick-removed" : ""}" data-fname="${_escapeAttr(m.filename)}">
      ${tag}<span>${label}</span>
    </div>`;
  }
  if (!choices.length) grid = '<p class="no-results">ไม่มีสื่อในโปรเจคนี้</p>';

  overlay.innerHTML = `<div class="sb-picker">
    <div class="sb-picker-header">
      <span>เลือก media — Scene ${sceneIdx + 1}</span>
      <button onclick="this.closest('.sb-picker-overlay').remove()">✕</button>
    </div>
    <div class="sb-picker-grid">${grid}</div>
  </div>`;

  overlay.querySelectorAll(".sb-pick-item").forEach((el) => {
    el.onclick = () => _pickMedia(sceneIdx, currentFilename, el.dataset.fname, overlay);
  });

  document.body.appendChild(overlay);
}

function _pickMedia(sceneIdx, currentFname, targetFname, overlay) {
  overlay.remove();
  if (!targetFname || currentFname === targetFname) return;

  while (_sbMediaFiles.length <= sceneIdx) _sbMediaFiles.push(null);
  const targetIdx = _sbMediaFiles.findIndex((m) => m && m.filename === targetFname);
  if (targetIdx >= 0) {
    const tmp = _sbMediaFiles[sceneIdx];
    _sbMediaFiles[sceneIdx] = _sbMediaFiles[targetIdx];
    _sbMediaFiles[targetIdx] = tmp;
  } else {
    // Bringing back a removed item; whatever was in this scene is removed instead.
    const r = _sbRemoved.findIndex((m) => m.filename === targetFname);
    if (r < 0) return;
    const [restored] = _sbRemoved.splice(r, 1);
    if (_sbMediaFiles[sceneIdx]) _sbRemoved.push(_sbMediaFiles[sceneIdx]);
    _sbMediaFiles[sceneIdx] = restored;
  }
  _markPreviewOutdated();
  _renderStoryboard();
}

function _sbRemoveMedia(idx) {
  const m = _sbMediaFiles[idx];
  if (!m) return;
  _sbRemoved.push(m);
  _sbMediaFiles[idx] = null;
  // A row left with neither media nor text has nothing to show.
  if (!(_sbScenes[idx] || "").trim()) {
    _sbMediaFiles.splice(idx, 1);
    _sbScenes.splice(idx, 1);
    _sbDurations.splice(idx, 1);
    _sbQueries.splice(idx, 1);
  }
  _markPreviewOutdated();
  _renderStoryboard();
  showToast("เอาสื่อออกแล้ว — คลิกช่องว่างเพื่อเลือกกลับมาได้");
}

function _escapeAttr(str) {
  return str.replace(/&/g, "&amp;").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}


// ── Drafts ──

let _currentDraftId = null;

function _collectFormState() {
  return {
    id: _currentDraftId,
    topic: document.getElementById("topicInput").value.trim(),
    voice: selectedVoice,
    rate: document.getElementById("rateSlider").value,
    pitch: document.getElementById("pitchSlider").value,
    tone: selectedTone,
    subtitles: subtitlesEnabled,
    persona: document.getElementById("personaInput").value.trim(),
    customScript: document.getElementById("customScriptInput").value.trim(),
    bgmFile: bgmFilename,
    bgmVolume: document.getElementById("bgmVolumeSlider").value,
    aspectRatios: selectedAspectRatios,
    mode: selectedMode,
    voiceB: selectedVoiceB,
    duration: selectedDuration,
    cloneVoiceId: cloneVoiceId,
    cloneTau: document.getElementById("tauSlider").value,
    toneVar: selectedTone === "custom" ? document.getElementById("customToneVar").value : 0,
    toneRate: selectedTone === "custom" ? document.getElementById("customToneRate").value : 0,
    tonePitch: selectedTone === "custom" ? document.getElementById("customTonePitch").value : 0,
    overlayText: (document.getElementById("overlayTextInput")?.value || "").trim(),
    overlayFont: document.getElementById("overlayFont")?.value || "",
    overlayAnimation: document.getElementById("overlayAnimation")?.value || "",
    mediaFiles: selectedMedia.map(m => m.filename),
    cloneEngine: selectedCloneEngine,
    runMode: selectedRunMode,
    mediaSource: selectedMediaSource,
    aiEngine: selectedAiEngine,
    graphics: selectedGraphics,
  };
}

function _restoreFormState(d) {
  document.getElementById("topicInput").value = d.topic || "";
  if (d.voice) selectVoice(d.voice);
  if (d.rate !== undefined) { document.getElementById("rateSlider").value = d.rate; updateRateLabel(); }
  if (d.pitch !== undefined) { document.getElementById("pitchSlider").value = d.pitch; updatePitchLabel(); }
  if (d.tone) {
    document.getElementById("toneSelect").value = d.tone;
    selectTone(d.tone);
    if (d.tone === "custom") {
      document.getElementById("customToneVar").value = d.toneVar ?? 10;
      document.getElementById("customToneRate").value = d.toneRate ?? 0;
      document.getElementById("customTonePitch").value = d.tonePitch ?? 0;
    }
  }
  if (d.subtitles !== undefined) toggleSubtitles(d.subtitles ? "on" : "off");
  if (d.persona) { document.getElementById("personaInput").value = d.persona; document.getElementById("personaInput")._userEdited = true; }
  document.getElementById("customScriptInput").value = d.customScript || "";
  updateScriptCounter();
  if (d.customScript || d.persona) document.getElementById("scriptCard").open = true;
  if (d.bgmVolume) { document.getElementById("bgmVolumeSlider").value = d.bgmVolume; updateBgmVolumeLabel(); }
  if (d.aspectRatios) {
    selectedAspectRatios = d.aspectRatios;
    document.querySelectorAll("[data-ratio]").forEach(b => b.classList.toggle("active", selectedAspectRatios.includes(b.dataset.ratio)));
    updateMediaAspectRatio();
  }
  if (d.mode) selectMode(d.mode);
  if (d.voiceB) selectVoiceB(d.voiceB);
  if (d.duration) selectDuration(d.duration);
  if (d.cloneTau) { document.getElementById("tauSlider").value = d.cloneTau; updateTauLabel(); }
  if (d.cloneEngine) { selectedCloneEngine = d.cloneEngine; document.getElementById("cloneEngineSelect").value = d.cloneEngine; }
  const cloneSel = document.getElementById("cloneVoiceSelect");
  const hasVoice = [...cloneSel.options].some((o) => o.value === (d.cloneVoiceId || ""));
  cloneSel.value = hasVoice ? (d.cloneVoiceId || "") : "";
  selectCloneVoice(cloneSel.value);
  document.getElementById("overlayTextInput").value = d.overlayText || "";
  const fontSel = document.getElementById("overlayFont");
  fontSel.value = [...fontSel.options].some((o) => o.value === d.overlayFont) ? d.overlayFont : "sarabun";
  if (d.overlayAnimation) document.getElementById("overlayAnimation").value = d.overlayAnimation;
  if (d.runMode) selectRunMode(d.runMode);
  if (d.mediaSource) selectMediaSource(d.mediaSource);
  if (d.aiEngine) { selectedAiEngine = d.aiEngine; document.getElementById("aiEngineSelect").value = d.aiEngine; }
  if (d.graphics) selectGraphics(d.graphics);
  _currentDraftId = d.id || null;
}

async function saveDraft() {
  const state = _collectFormState();
  if (!state.topic) return showToast("กรุณาใส่หัวข้อก่อนบันทึก", true);
  try {
    const resp = await fetch("/api/drafts/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state) });
    const data = await resp.json();
    _currentDraftId = data.id;
    showToast(`บันทึกร่างแล้ว (${data.saved_at})`);
  } catch { showToast("บันทึกไม่สำเร็จ", true); }
}

async function openDrafts() {
  const list = document.getElementById("draftsList");
  list.innerHTML = '<p class="loading">กำลังโหลด...</p>';
  document.getElementById("draftsModal").classList.remove("hidden");
  try {
    const resp = await fetch("/api/drafts");
    const drafts = await resp.json();
    if (!drafts.length) { list.innerHTML = '<p class="no-results">ยังไม่มีร่างที่บันทึกไว้</p>'; return; }
    const toneNames = { normal: "ปกติ", cheerful: "สนุกสนาน", energetic: "ตื่นเต้น", warm: "อบอุ่น", serious: "จริงจัง", news: "ข่าว", custom: "กำหนดเอง" };
    list.innerHTML = drafts.map(d => `
      <div class="draft-item" onclick="loadDraft('${d.id}')">
        <div class="draft-info">
          <div class="draft-title">${d.topic || "(ไม่มีหัวข้อ)"}</div>
          <div class="draft-meta">${d.saved_at} · ${d.mode === "dialogue" ? "สนทนา" : "บรรยาย"} · ${toneNames[d.tone] || d.tone}</div>
        </div>
        <button class="draft-delete" onclick="event.stopPropagation();deleteDraft('${d.id}')" title="ลบ">&times;</button>
      </div>
    `).join("");
  } catch { list.innerHTML = '<p class="no-results">โหลดไม่สำเร็จ</p>'; }
}

function closeDrafts() { document.getElementById("draftsModal").classList.add("hidden"); }

async function loadDraft(id) {
  try {
    const resp = await fetch(`/api/drafts/${id}`);
    const data = await resp.json();
    _restoreFormState(data);
    closeDrafts();
    showToast("โหลดร่างแล้ว");
  } catch { showToast("โหลดไม่สำเร็จ", true); }
}

async function deleteDraft(id) {
  try {
    await fetch(`/api/drafts/${id}`, { method: "DELETE" });
    if (_currentDraftId === id) _currentDraftId = null;
    openDrafts();
  } catch { showToast("ลบไม่สำเร็จ", true); }
}

function _canOpenStoryboard(p) {
  return p.phase === "media_ready" || (p.phase === "error" && p.render_params && p.audio_path);
}

async function loadProject(projectId) {
  try {
    const resp = await fetch(`/api/status/${projectId}`);
    const data = await resp.json();
    currentProjectId = projectId;
    _rememberProject(currentProjectId);
    generateStartTime = null;
    if (data.phase === "done") {
      showResult(data);
    } else if (_canOpenStoryboard(data)) {
      showStoryboardPreview(data);
    } else if (!["error", "done"].includes(data.phase)) {
      _showWorkSection("progressSection", data.topic);
      updateProgress(data.progress, data.phase);
      pollStatus();
    }
  } catch (e) {
    showToast("โหลดโปรเจคไม่ได้", true);
  }
}

const HISTORY_PAGE = 20;
let _historyLimit = HISTORY_PAGE;

function showMoreHistory() {
  _historyLimit += HISTORY_PAGE;
  loadHistory();
}

async function loadHistory() {
  try {
    const resp = await fetch("/api/projects");
    const projects = (await resp.json()).sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
    document.getElementById("historyList").innerHTML = projects.slice(0, _historyLimit).map((p) => {
      const openable = p.phase === "done" || _canOpenStoryboard(p) || !["error", "done"].includes(p.phase);
      const statusLabel = _canOpenStoryboard(p) && p.phase === "error" ? "ล้มเหลว — กดเพื่อลองใหม่" : (PHASE_LABELS[p.phase] || p.phase);
      return `<div class="history-item ${openable ? "clickable" : ""}" ${openable ? `onclick="loadProject('${p.project_id}')"` : ""}>
        <span class="topic">${escapeHtml(p.topic)}</span>
        <span class="status ${p.phase}">${statusLabel}</span>
        <button class="rebuild-btn" onclick="event.stopPropagation();rebuildProject('${p.project_id}')" title="ใช้หัวข้อ/สคริปต์นี้สร้างใหม่">&#8635;</button>
      </div>`;
    }).join("");
    document.getElementById("historyMoreBtn").classList.toggle("hidden", projects.length <= _historyLimit);
  } catch (e) {
    /* history is non-critical */
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
      document.getElementById("scriptCard").open = true;
      document.getElementById("customScriptInput").value = data.script;
      updateScriptCounter();
    }
    document.getElementById("setupPanel").scrollTo({ top: 0, behavior: "smooth" });
    window.scrollTo({ top: 0, behavior: "smooth" });
    showToast("โหลดโปรเจคเก่าแล้ว — แก้ไขแล้วกด สร้างคลิป");
  } catch (e) {
    showToast("โหลดโปรเจคไม่ได้", true);
  }
}

// ── Voice Clone ──

function selectCloneVoice(voiceId) {
  cloneVoiceId = voiceId;
  for (const id of ["cloneVoiceInfo", "cloneTauRow", "cloneEngineSelect"]) {
    document.getElementById(id).classList.toggle("hidden", !voiceId);
  }
  if (voiceId) {
    const sel = document.getElementById("cloneVoiceSelect");
    document.getElementById("cloneVoiceName").textContent = sel.options[sel.selectedIndex].text;
    document.getElementById("clonePreview").src = `/api/voices/${voiceId}/preview`;
  } else {
    document.getElementById("clonePreview").removeAttribute("src");
  }
  _updateCloneDependentRows();
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
  document.getElementById("cloneVoiceSelect").value = "";
  selectCloneVoice("");
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
    document.querySelectorAll(".compare-open-btn").forEach((b) => b.classList.toggle("hidden", !voices.length));
  } catch {}
}

// ── Voice presets ──

let _voicePresets = [];
const VOICE_NAMES = { female: "หญิง (เปรมวดี)", male: "ชาย (นิวัตน์)" };
const TONE_NAMES = { normal: "ปกติ", cheerful: "สนุกสนาน", energetic: "ตื่นเต้น", warm: "อบอุ่น", serious: "จริงจัง", news: "ผู้ประกาศข่าว", custom: "กำหนดเอง" };
const CLONE_ENGINE_NAMES = { openvoice: "OpenVoice V2", "f5-tts-thai": "F5-TTS-THAI" };

const _signed = (v, unit) => (v > 0 ? `+${v}${unit}` : v < 0 ? `${v}${unit}` : "ปกติ");

function describeVoicePreset(p) {
  const parts = [`ต้นฉบับ: ${VOICE_NAMES[p.voice] || p.voice}`];
  if (p.clone_voice_id) {
    const name = p.clone_missing ? "(เสียงโคลนถูกลบไปแล้ว)" : p.clone_name;
    parts.push(`โคลนด้วย: ${name} · ${CLONE_ENGINE_NAMES[p.clone_engine] || p.clone_engine}`);
    parts.push(`ระดับโคลน ${(p.tau / 100).toFixed(2)}`);
  } else {
    parts.push("ไม่โคลน");
  }
  parts.push(`ความเร็ว ${_signed(p.rate, "%")}`, `ระดับเสียง ${_signed(p.pitch, "Hz")}`, `โทน: ${TONE_NAMES[p.tone] || p.tone}`);
  return parts.join(" · ");
}

async function loadVoicePresets(selectId) {
  try {
    _voicePresets = await (await fetch("/api/voice-presets")).json();
  } catch { _voicePresets = []; }
  const sel = document.getElementById("voicePresetSelect");
  sel.innerHTML = '<option value="">— ชุดเสียงที่บันทึกไว้ —</option>' +
    _voicePresets.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
  sel.value = selectId || "";
  _showPresetInfo(sel.value);
}

function _showPresetInfo(id) {
  const p = _voicePresets.find((x) => x.id === id);
  const info = document.getElementById("voicePresetInfo");
  info.textContent = p ? describeVoicePreset(p) : "";
  info.classList.toggle("hidden", !p);
  document.getElementById("deletePresetBtn").classList.toggle("hidden", !p);
}

function applyVoicePreset(id) {
  _showPresetInfo(id);
  const p = _voicePresets.find((x) => x.id === id);
  if (!p) return;
  selectVoice(p.voice);
  document.getElementById("rateSlider").value = p.rate; updateRateLabel();
  document.getElementById("pitchSlider").value = p.pitch; updatePitchLabel();
  document.getElementById("toneSelect").value = p.tone; selectTone(p.tone);
  if (p.tone === "custom" && p.tone_custom) {
    document.getElementById("customToneVar").value = p.tone_custom.variation ?? 10;
    document.getElementById("customToneRate").value = p.tone_custom.rate ?? 0;
    document.getElementById("customTonePitch").value = p.tone_custom.pitch ?? 0;
  }
  selectedCloneEngine = p.clone_engine;
  document.getElementById("cloneEngineSelect").value = p.clone_engine;
  document.getElementById("tauSlider").value = p.tau; updateTauLabel();
  const cloneSel = document.getElementById("cloneVoiceSelect");
  const available = p.clone_voice_id && [...cloneSel.options].some((o) => o.value === p.clone_voice_id);
  cloneSel.value = available ? p.clone_voice_id : "";
  selectCloneVoice(cloneSel.value);
  if (p.clone_voice_id && !available) showToast("เสียงโคลนของชุดนี้ถูกลบไปแล้ว — ใช้เสียง TTS ปกติแทน", true);
  else showToast(`ใช้ชุดเสียง "${p.name}" แล้ว`);
}

async function _postVoicePreset(preset) {
  const resp = await fetch("/api/voice-presets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(preset),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || "บันทึกไม่สำเร็จ");
  return data;
}

async function saveVoicePreset() {
  const tau = parseInt(document.getElementById("tauSlider").value);
  const cloneName = cloneVoiceId
    ? document.getElementById("cloneVoiceSelect").selectedOptions[0].text.replace(/\s*\([\d.]+s\)$/, "")
    : "";
  const suggested = cloneName
    ? `${cloneName} · ${TONE_NAMES[selectedTone]} · โคลน ${(tau / 100).toFixed(2)}`
    : `${VOICE_NAMES[selectedVoice]} · ${TONE_NAMES[selectedTone]}`;
  const name = prompt("ตั้งชื่อชุดเสียง (ชื่อซ้ำจะบันทึกทับ):", suggested);
  if (!name) return;
  try {
    const saved = await _postVoicePreset({
      name,
      voice: selectedVoice,
      rate: parseInt(document.getElementById("rateSlider").value),
      pitch: parseInt(document.getElementById("pitchSlider").value),
      tone: selectedTone,
      tone_custom: selectedTone === "custom" ? {
        variation: parseInt(document.getElementById("customToneVar").value) || 10,
        rate: parseInt(document.getElementById("customToneRate").value) || 0,
        pitch: parseInt(document.getElementById("customTonePitch").value) || 0,
      } : null,
      clone_voice_id: cloneVoiceId,
      clone_engine: selectedCloneEngine,
      tau,
    });
    await loadVoicePresets(saved.id);
    showToast(`บันทึกชุดเสียง "${saved.name}" แล้ว`);
  } catch (e) {
    showToast(e.message, true);
  }
}

async function deleteVoicePreset() {
  const id = document.getElementById("voicePresetSelect").value;
  const p = _voicePresets.find((x) => x.id === id);
  if (!p || !confirm(`ลบชุดเสียง "${p.name}"?`)) return;
  await fetch(`/api/voice-presets/${id}`, { method: "DELETE" });
  await loadVoicePresets();
  showToast("ลบชุดเสียงแล้ว");
}

// The compare job always uses Premwadee at normal speed/pitch as the base,
// with OpenVoice and the modal's tau, so that is exactly what gets saved.
async function saveComparedVoice(voiceId, voiceName) {
  const tau = _compareJobTau;
  const name = prompt("ตั้งชื่อชุดเสียง (ชื่อซ้ำจะบันทึกทับ):", `${voiceName} · โคลน ${(tau / 100).toFixed(2)}`);
  if (!name) return;
  try {
    const saved = await _postVoicePreset({
      name, voice: "female", rate: 0, pitch: 0, tone: "normal",
      clone_voice_id: voiceId, clone_engine: "openvoice", tau, source: "compare",
    });
    await loadVoicePresets(document.getElementById("voicePresetSelect").value);
    showToast(`บันทึกชุดเสียง "${saved.name}" แล้ว — เลือกใช้ได้ที่ "ชุดเสียง"`);
  } catch (e) {
    showToast(e.message, true);
  }
}

// ── Compare All Voices ──

let _compareJobTau = 30;

let _compareVoices = [];
let _comparePollTimer = null;

async function openCompareVoices() {
  try {
    const resp = await fetch("/api/voices");
    _compareVoices = await resp.json();
  } catch { _compareVoices = []; }

  document.getElementById("compareProgress").classList.add("hidden");
  const tau = document.getElementById("tauSlider").value;
  document.getElementById("compareTauSlider").value = tau;
  document.getElementById("compareTauVal").textContent = (tau / 100).toFixed(2);
  const btn = document.getElementById("compareStartBtn");
  btn.disabled = false;
  btn.textContent = "เริ่มเทียบ";

  if (!_compareVoices.length) {
    document.getElementById("compareVoicesList").innerHTML =
      '<p class="no-results">ยังไม่มีเสียงโคลนที่บันทึกไว้ — อัปโหลดเสียงก่อน</p>';
  } else {
    _renderCompareList(_compareVoices.map((v) => ({ id: v.id, name: v.name, status: "idle" })), true);
  }
  document.getElementById("compareVoicesModal").classList.remove("hidden");
}

function closeCompareVoices() {
  document.getElementById("compareVoicesModal").classList.add("hidden");
  if (_comparePollTimer) { clearInterval(_comparePollTimer); _comparePollTimer = null; }
}

function _renderCompareList(results, showCheckbox) {
  const el = document.getElementById("compareVoicesList");
  const icons = { idle: "&#9676;", pending: "&#8987;", done: "&#9989;", error: "&#10060;" };
  let html = "";
  if (showCheckbox) {
    html += `<div class="compare-select-all">
      <label><input type="checkbox" id="compareSelectAll" onchange="toggleCompareAll(this.checked)"> เลือกทั้งหมด</label>
    </div>`;
  }
  html += results.map((r) => {
    const icon = icons[r.status] || icons.idle;
    const player = r.status === "done" && r._jobId
      ? `<audio controls preload="none" src="/api/compare-voices/audio/${r._jobId}/${r.id}"></audio>
         <button class="compare-save-btn" title="บันทึกเป็นชุดเสียง" onclick="saveComparedVoice('${r.id}', '${escapeHtml(r.name).replace(/'/g, "\\'")}')">💾 บันทึก</button>`
      : r.status === "error"
        ? `<span class="compare-err" title="${escapeHtml(r.error || "")}">ไม่สำเร็จ</span>`
        : "";
    const checkbox = showCheckbox
      ? `<input type="checkbox" class="compare-check" data-voice-id="${r.id}">`
      : "";
    return `<div class="repl-item compare-row">
      <div class="repl-view">${checkbox}<span class="compare-icon">${icon}</span> ${escapeHtml(r.name)}</div>
      <div class="compare-player">${player}</div>
    </div>`;
  }).join("");
  el.innerHTML = html;
}

function toggleCompareAll(checked) {
  document.querySelectorAll(".compare-check").forEach((cb) => { cb.checked = checked; });
}

async function clearCompareAudio() {
  document.querySelectorAll(".compare-player audio").forEach((a) => {
    a.pause(); a.removeAttribute("src"); a.load();
  });
  if (_comparePollTimer) { clearInterval(_comparePollTimer); _comparePollTimer = null; }
  try { await fetch("/api/compare-voices/clear", { method: "DELETE" }); } catch {}
  _renderCompareList(_compareVoices.map((v) => ({ id: v.id, name: v.name, status: "idle" })), true);
  showToast("เคลียเสียงเทียบแล้ว");
}

async function startCompareVoices() {
  const text = document.getElementById("compareText").value.trim();
  if (!text) return showToast("กรุณาใส่ข้อความทดสอบ", true);
  if (!_compareVoices.length) return;

  const selected = Array.from(document.querySelectorAll(".compare-check:checked"))
    .map((cb) => cb.dataset.voiceId);
  if (!selected.length) return showToast("กรุณาเลือกเสียงอย่างน้อย 1 รายการ", true);

  const btn = document.getElementById("compareStartBtn");
  btn.disabled = true;
  btn.textContent = "กำลังเริ่ม...";
  const progress = document.getElementById("compareProgress");
  progress.classList.remove("hidden");
  progress.textContent = `กำลังโหลดโมเดล OpenVoice แล้วเทียบ ${selected.length} เสียง...`;

  _compareJobTau = parseInt(document.getElementById("compareTauSlider").value);
  try {
    const resp = await fetch("/api/compare-voices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice_ids: selected, tau: _compareJobTau / 100 }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "เริ่มเทียบเสียงไม่สำเร็จ");

    btn.textContent = "กำลังเทียบ...";
    _pollCompareStatus(data.job_id, data.total);
  } catch (e) {
    showToast(e.message || "เริ่มเทียบเสียงไม่สำเร็จ", true);
    btn.disabled = false;
    btn.textContent = "เริ่มเทียบ";
    progress.classList.add("hidden");
  }
}

function _pollCompareStatus(jobId, total) {
  if (_comparePollTimer) clearInterval(_comparePollTimer);
  const progress = document.getElementById("compareProgress");
  const btn = document.getElementById("compareStartBtn");

  _comparePollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/compare-voices/status/${jobId}`);
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.error || "โหลดสถานะไม่สำเร็จ");

      const results = data.results.map((r) => ({ ...r, _jobId: jobId }));
      _renderCompareList(results);
      const doneCount = results.filter((r) => r.status === "done" || r.status === "error").length;
      progress.textContent = `เทียบแล้ว ${doneCount}/${total} เสียง...`;

      if (data.status === "done") {
        clearInterval(_comparePollTimer);
        _comparePollTimer = null;
        progress.textContent = `เสร็จแล้ว — เทียบ ${total} เสียง`;
        btn.disabled = false;
        btn.textContent = "เริ่มเทียบ";
      } else if (data.status === "error") {
        clearInterval(_comparePollTimer);
        _comparePollTimer = null;
        showToast(data.error || "เทียบเสียงไม่สำเร็จ", true);
        btn.disabled = false;
        btn.textContent = "เริ่มเทียบ";
      }
    } catch (e) {
      clearInterval(_comparePollTimer);
      _comparePollTimer = null;
      showToast(e.message || "โหลดสถานะไม่สำเร็จ", true);
      btn.disabled = false;
      btn.textContent = "เริ่มเทียบ";
    }
  }, 1200);
}

// ── Visual Templates ──

let _templates = [];
let _selectedTemplate = null;
let _templatePhotos = {};

async function openTemplates() {
  try {
    const resp = await fetch("/api/templates");
    _templates = await resp.json();
  } catch { _templates = []; }
  _selectedTemplate = null;
  _templatePhotos = {};
  _renderTemplateGrid();
  document.getElementById("templatesModal").classList.remove("hidden");
}

function closeTemplates() {
  document.getElementById("templatesModal").classList.add("hidden");
}

function _renderTemplateGrid() {
  document.getElementById("templatesHeaderTitle").textContent = "เทมเพลตภาพ";
  const body = document.getElementById("templatesBody");
  if (!_templates.length) {
    body.innerHTML = '<p class="no-results">โหลดเทมเพลตไม่สำเร็จ</p>';
    return;
  }
  body.innerHTML = `<div class="tpl-grid">${_templates.map((t) => `
    <div class="tpl-card" onclick="selectTemplate('${t.id}')">
      <div class="tpl-card-name">${escapeHtml(t.name)}</div>
      <div class="tpl-card-desc">${escapeHtml(t.description)}</div>
    </div>`).join("")}</div>`;
}

function selectTemplate(id) {
  _selectedTemplate = _templates.find((t) => t.id === id);
  if (!_selectedTemplate) return;
  _templatePhotos = {};
  document.getElementById("templatesHeaderTitle").textContent = _selectedTemplate.name;
  _renderTemplateForm();
}

function _renderTemplateForm() {
  const t = _selectedTemplate;
  const body = document.getElementById("templatesBody");

  const photoInputs = t.photos.map((p) => `
    <div class="tpl-field">
      <label>${escapeHtml(p.label)}</label>
      <input type="file" accept="image/*" onchange="_setTemplatePhoto('${p.key}', this.files[0])">
      <div class="tpl-photo-preview" id="tplPhotoPreview_${p.key}"></div>
    </div>`).join("");

  const fieldInputs = t.fields.map((f) => {
    const id = `tplField_${f.key}`;
    if (f.type === "textarea") {
      return `<div class="tpl-field"><label>${escapeHtml(f.label)}</label>
        <textarea id="${id}" placeholder="${escapeHtml(f.placeholder || "")}" rows="2"></textarea></div>`;
    }
    if (f.type === "checkbox") {
      return `<div class="tpl-field tpl-field-checkbox">
        <label><input type="checkbox" id="${id}" ${f.default ? "checked" : ""}> ${escapeHtml(f.label)}</label></div>`;
    }
    if (f.type === "color") {
      return `<div class="tpl-field"><label>${escapeHtml(f.label)}</label>
        <input type="color" id="${id}" value="${f.default || "#000000"}"></div>`;
    }
    if (f.type === "select") {
      const opts = (f.options || []).map((o) => `<option value="${o.value}">${escapeHtml(o.label)}</option>`).join("");
      return `<div class="tpl-field"><label>${escapeHtml(f.label)}</label>
        <select id="${id}">${opts}</select></div>`;
    }
    return `<div class="tpl-field"><label>${escapeHtml(f.label)}</label>
      <input type="text" id="${id}" placeholder="${escapeHtml(f.placeholder || "")}"></div>`;
  }).join("");

  const videoOverlayBtn = t.type === "both"
    ? `<button class="clear-btn" id="tplOverlayBtn" onclick="useAsVideoOverlay()" title="ใช้ซ้อนบนวิดีโอที่กำลังจะสร้าง แทนที่จะสร้างเป็นภาพนิ่ง">ใช้เป็น Overlay วิดีโอ</button>`
    : "";
  const videoOverlayNote = t.type === "both"
    ? `<div class="tpl-overlay-note">* เมื่อใช้เป็น overlay วิดีโอ ไม่ต้องอัปโหลดรูป (ใช้คลิปพื้นหลังที่สร้างแทน) แนะนำปิดซับไตเติ้ล/ข้อความ overlay อื่น เพื่อไม่ให้ซ้อนทับกัน</div>`
    : "";

  body.innerHTML = `
    <div class="tpl-back"><button class="clear-btn" onclick="_renderTemplateGrid()">&larr; เลือกเทมเพลตอื่น</button></div>
    <div class="tpl-form">${photoInputs}${fieldInputs}</div>
    ${videoOverlayNote}
    <div class="crop-actions">
      <button class="generate-btn" id="tplRenderBtn" onclick="renderTemplateImage()">สร้างภาพ</button>
      ${videoOverlayBtn}
    </div>
    <div id="tplResult"></div>
  `;
}

function _readTemplateFields(t) {
  const fields = {};
  for (const f of t.fields) {
    const el = document.getElementById(`tplField_${f.key}`);
    if (!el) continue;
    fields[f.key] = f.type === "checkbox" ? el.checked : el.value;
  }
  return fields;
}

let videoTemplateFields = null;

function useAsVideoOverlay() {
  const t = _selectedTemplate;
  videoTemplateFields = _readTemplateFields(t);
  showToast("ตั้งค่า overlay วิดีโอแล้ว — จะใช้ตอนกด \"สร้างคลิป\" ครั้งถัดไป");
  _updateVideoOverlayBadge();
  closeTemplates();
}

function clearVideoOverlay() {
  videoTemplateFields = null;
  _updateVideoOverlayBadge();
}

function _updateVideoOverlayBadge() {
  const el = document.getElementById("videoOverlayBadge");
  if (!el) return;
  el.classList.toggle("hidden", !videoTemplateFields);
}

function _setTemplatePhoto(key, file) {
  if (!file) return;
  _templatePhotos[key] = file;
  const preview = document.getElementById(`tplPhotoPreview_${key}`);
  const url = URL.createObjectURL(file);
  preview.innerHTML = `<img src="${url}" alt="">`;
}

async function renderTemplateImage() {
  const t = _selectedTemplate;
  for (const p of t.photos) {
    if (!_templatePhotos[p.key]) return showToast(`กรุณาเลือก: ${p.label}`, true);
  }

  const fields = _readTemplateFields(t);

  const btn = document.getElementById("tplRenderBtn");
  btn.disabled = true;
  btn.textContent = "กำลังสร้าง...";

  const formData = new FormData();
  formData.set("template_id", t.id);
  formData.set("fields", JSON.stringify(fields));
  for (const p of t.photos) {
    formData.set(p.key, _templatePhotos[p.key]);
  }

  try {
    const resp = await fetch("/api/templates/render", { method: "POST", body: formData });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "สร้างภาพไม่สำเร็จ");
    const url = data.url + "?t=" + Date.now();
    document.getElementById("tplResult").innerHTML = `
      <div class="tpl-result">
        <img src="${url}" alt="ผลลัพธ์">
        <a class="generate-btn tpl-download" href="${url}" download="template.png">ดาวน์โหลด</a>
      </div>`;
  } catch (e) {
    showToast(e.message || "สร้างภาพไม่สำเร็จ", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "สร้างภาพ";
  }
}

// ── Help system ──

const HELP_TEXTS = {
  run_mode: {
    title: "โหมดทำงาน",
    body: "<b>กึ่งอัตโนมัติ</b> — ระบบเดิม: เขียนสคริปต์ สร้างเสียง ดึงสื่อจากหัวข้อ แล้วหยุดให้จัด Storyboard\n\n<b>อัตโนมัติ + หยุดตรวจ</b> — สคริปต์แบ่งเป็นฉาก หาสื่อตรงทีละฉาก ภาพเปลี่ยนตามจังหวะพูด แล้วหยุดให้ตรวจ/ดูตัวอย่างหนึ่งครั้งก่อนสร้างวิดีโอ\n\n<b>อัตโนมัติเต็ม</b> — เหมือนแบบหยุดตรวจ แต่ถ้าผ่านด่านตรวจคุณภาพ (เสียงถูกต้อง ความยาวพอดี สื่อครบทุกฉาก) จะสร้างวิดีโอให้เลย ถ้าไม่ผ่านจะหยุดพร้อมบอกเหตุผล\n\nทุกโหมด: เมื่อเสร็จจะได้ชื่อคลิป คำอธิบาย แฮชแทก ภาพปก และบันทึกลง F:\\LocalAI\\clips อัตโนมัติ"
  },
  media_source: {
    title: "แหล่งสื่อ",
    body: "<b>Pexels</b> — คลิป/ภาพจริงจาก Pexels ตามคำค้นของแต่ละฉาก\n\n<b>Pexels + ภาพ AI</b> — ใช้คลิป Pexels ก่อน ฉากไหนหาไม่ได้ให้ AI วาด\n\n<b>ภาพ AI</b> — ให้ AI วาดทุกฉาก (AI-Bridge-Launcher)\n\n<b>FLUX.2 klein</b> วาดในเครื่อง ภาพแรกโหลดโมเดลประมาณ 1 นาที จากนั้นประมาณ 30 วินาทีต่อภาพ (โหมดเร็ว 15 วินาที)\n<b>Gemini</b> วาดบนคลาวด์ เร็ว แต่คิดเงินต่อภาพ\n\nใน Storyboard กดปุ่ม 🎨 ที่ฉากใดก็ได้เพื่อสร้างภาพ AI ให้ฉากนั้นเอง"
  },
  graphics: {
    title: "การ์ดตัวเลข",
    body: "ฉากที่พูดถึงตัวเลขสำคัญ (สถิติ ราคา เปอร์เซ็นต์) จะกลายเป็นการ์ดกราฟิกเคลื่อนไหว: ตัวเลขนับขึ้นจาก 0 พร้อมหน่วย ป้าย และคำอธิบาย สร้างด้วย HyperFrames ในเครื่อง ประมาณ 20 วินาทีต่อการ์ด\n\n<b>ตัวเลขบนการ์ดต้องมีอยู่ในคำพูดของฉากนั้นจริง</b> — AI แค่ชี้ว่าฉากไหนมีตัวเลข ระบบตรวจซ้ำด้วยโค้ด ถ้าไม่ตรงจะไม่ทำการ์ดและใช้ภาพตามปกติ\n\nไม่เกิน 1 ใน 3 ของจำนวนฉาก และไม่ใช้กับฉากสุดท้าย (CTA) ฉากอื่นใช้สื่อตามแหล่งที่เลือกไว้\n\nใน Storyboard กดปุ่ม 📊 ที่ฉากใดก็ได้เพื่อพิมพ์ตัวเลขแล้วสร้างการ์ดเอง"
  },
  voice_preset: {
    title: "ชุดเสียง",
    body: "บันทึกการตั้งค่าเสียงที่ทดลองแล้วว่าดี เพื่อใช้ครั้งต่อไปด้วยคลิกเดียว\n\n<b>สิ่งที่บันทึก:</b> เสียงต้นฉบับ (เปรมวดี/นิวัตน์), เสียงโคลนและเครื่องโคลน, ระดับโคลน, ความเร็ว, ระดับเสียง และโทนเสียง\n\n<b>บันทึกได้ 2 ทาง:</b>\n• ปุ่ม 💾 บันทึกชุดเสียง = บันทึกค่าที่ตั้งอยู่ตอนนี้\n• ปุ่ม 💾 บันทึก ในหน้าต่างเทียบเสียง = บันทึกเสียงที่ฟังแล้วชอบ (ต้นฉบับเปรมวดี ความเร็วปกติ OpenVoice และระดับโคลนที่ใช้เทียบ)\n\nเลือกชุดเสียงจากรายการ = ตั้งค่าทั้งหมดให้ทันที\nตั้งชื่อซ้ำกับชุดเดิม = บันทึกทับ"
  },
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
  duration: {
    title: "ความยาวคลิป",
    body: "เลือกความยาวของวิดีโอที่จะสร้าง\n\n<b>Shorts (45-60 วินาที)</b> — สำหรับ YouTube Shorts / TikTok / Reels\nใช้สื่อ 4 คลิป, สคริปต์ 5 ส่วน\n\n<b>ปานกลาง (2-3 นาที)</b> — เนื้อหาละเอียดขึ้น\nใช้สื่อ 8 คลิป, สคริปต์ 8 ส่วน\n\n<b>ยาว (3-5 นาที)</b> — เนื้อหาเชิงลึก\nใช้สื่อ 12 คลิป, สคริปต์ 11 ส่วน\n\nตัวนับสคริปต์จะปรับ threshold ตามความยาวที่เลือก"
  },
  tau: {
    title: "ระดับการโคลนเสียง (tau)",
    body: "ควบคุมความเข้มในการแปลงเสียงให้เหมือนเสียงอ้างอิง\n\n<b>ค่าต่ำ (0.10-0.20)</b> — เสียงชัด คุณภาพดี แต่ยังคล้ายเสียง TTS ต้นทาง\n<b>ค่ากลาง (0.25-0.35)</b> — สมดุลระหว่างความชัดกับความเหมือน (แนะนำ)\n<b>ค่าสูง (0.40-0.80)</b> — เหมือนเสียงอ้างอิงมาก แต่อาจมี artifact\n\n<b>คำแนะนำเสียงอ้างอิง:</b>\n• ยาว 20-30 วินาที (ไม่ต่ำกว่า 10 วินาที)\n• ผู้พูดคนเดียว พูดชัด\n• ไม่มีเสียงรบกวน/เพลงประกอบ\n• ใช้ไฟล์ WAV จะได้คุณภาพดีที่สุด"
  },
  clone: {
    title: "โคลนเสียง",
    body: "ใช้ AI โคลนน้ำเสียงจากไฟล์เสียงที่อัปโหลด\n\n<b>เลือก Clone Engine:</b>\n\n<b>OpenVoice V2</b> — สร้างเสียง TTS ก่อน แล้วแปลงน้ำเสียง (2 ขั้นตอน)\nใช้ .venv-clone (Python 3.12 + torch)\n\n<b>F5-TTS-THAI</b> — สร้างเสียงจาก reference โดยตรง (1 ขั้นตอน)\nใช้ .venv-f5 แยกต่างหาก (เพราะ numpy ชนกับ OpenVoice)\nต้องการ GPU — ระบบจะตัด reference ให้เหลือ 8 วินาที และจำคำถอดเสียงไว้ใช้ซ้ำ (ครั้งแรกจะช้ากว่า)\nความเร็ว/ระดับเสียงไม่มีผลกับ F5 จึงถูกซ่อนไว้\n\n<b>ติดตั้ง F5-TTS-THAI:</b>\npython -m venv .venv-f5\n.venv-f5\\Scripts\\python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124\n.venv-f5\\Scripts\\python -m pip install --only-binary=:all: numpy==1.26.4 scikit-learn==1.6.1\n.venv-f5\\Scripts\\python -m pip install git+https://github.com/VYNCX/F5-TTS-THAI.git\n.venv-f5\\Scripts\\python -m pip install pyarrow==17.0.0 datasets==2.21.0\n.venv-f5\\Scripts\\python -m pip uninstall -y torchcodec\n(สองบรรทัดสุดท้ายแก้ conflict ภายในแพ็กเกจ F5 เอง — pyarrow ใหม่ต้องการ numpy 2, torchcodec ชน DLL กับ torch 2.6)\n\n<b>วิธีใช้:</b>\n1. เลือก Clone Engine\n2. กด \"+ อัปโหลดเสียง\" เลือกไฟล์เสียงพูดชัดๆ 5-30 วินาที\n3. ตั้งชื่อเสียง แล้วเลือกจาก dropdown\n\n<b>เทียบเสียง</b> = ฟังทุกเสียงที่เลือกด้วยข้อความเดียวกัน (ใช้ OpenVoice)\n<b>เคลียเสียง</b> = ลบไฟล์เสียงทดสอบออกจากดิสก์\n\n<b>ไม่ใช้</b> = ใช้เสียง TTS ปกติ"
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
loadCloneEngines();

// ── Run mode, media source, AI images ──

let selectedRunMode = "semi";
let selectedMediaSource = "pexels";
let selectedAiEngine = "flux";
let _aiImagesAvailable = false;
let _sbScenesInfo = [];

function _updateModeRows() {
  const sceneMode = selectedRunMode !== "semi";
  document.querySelectorAll(".scene-only").forEach((el) => el.classList.toggle("hidden", !sceneMode));
  const aiRow = document.querySelector(".ai-only");
  if (aiRow) aiRow.classList.toggle("hidden", !sceneMode || selectedMediaSource === "pexels");
}

function selectRunMode(mode) {
  selectedRunMode = mode;
  document.querySelectorAll("[data-runmode]").forEach((b) => b.classList.toggle("active", b.dataset.runmode === mode));
  _updateModeRows();
}

function selectMediaSource(src) {
  if (src !== "pexels" && !_aiImagesAvailable) {
    showToast("ไม่พบ AI-Bridge-Launcher (F:\\enterprise\\aipass-auto-router) — ใช้ Pexels", true);
    src = "pexels";
  }
  selectedMediaSource = src;
  document.querySelectorAll("[data-msource]").forEach((b) => b.classList.toggle("active", b.dataset.msource === src));
  _updateModeRows();
}

async function loadAiImageStatus() {
  try {
    _aiImagesAvailable = (await (await fetch("/api/ai-image/status")).json()).available;
  } catch { _aiImagesAvailable = false; }
}

function _renderReviewBox(data) {
  const box = document.getElementById("sbReview");
  const reasons = data.review_reasons || [];
  if (data.phase === "media_ready" && reasons.length) {
    box.innerHTML = `<b>⚠ ต้องตรวจก่อนสร้างวิดีโอ</b><ul>${reasons.map((r) => `<li>${escapeHtml(r)}</li>`).join("")}</ul>`;
    box.classList.remove("hidden");
  } else {
    box.classList.add("hidden");
  }
}

function _renderPostInfo(data) {
  const box = document.getElementById("postInfo");
  const post = data.post;
  if (!post || data.phase !== "done") { box.classList.add("hidden"); return; }
  const tags = (post.hashtags || []).join(" ");
  const block = (label, key, text) => text ? `<div class="post-row">
      <div class="post-head"><b>${label}</b><button class="tool-btn" onclick="copyPostText('${key}')">คัดลอก</button></div>
      <div class="post-text" id="post_${key}">${escapeHtml(text)}</div></div>` : "";
  box.innerHTML = `
    <div class="post-grid">
      <img class="post-thumb" src="/api/project/${data.project_id}/thumbnail?t=${data.updated_at || ""}" alt="ภาพปก"
           onerror="this.style.display='none'">
      <div class="post-fields">
        ${block("ชื่อคลิป", "title", post.title)}
        ${block("คำอธิบาย", "description", post.description)}
        ${block("แฮชแทก", "hashtags", tags)}
        <div class="post-head"><button class="tool-btn" onclick="copyPostText('all')">คัดลอกทั้งหมด</button>
          <a class="tool-btn" href="/api/project/${data.project_id}/thumbnail" download="thumbnail.jpg">⬇ ภาพปก</a></div>
        ${data.clips_folder ? `<div class="post-folder">📁 บันทึกไว้ที่ ${escapeHtml(data.clips_folder)}</div>` : ""}
      </div>
    </div>`;
  box.classList.remove("hidden");
}

async function copyPostText(key) {
  const get = (k) => document.getElementById(`post_${k}`)?.textContent || "";
  const text = key === "all" ? ["title", "description", "hashtags"].map(get).filter(Boolean).join("\n\n") : get(key);
  try {
    await navigator.clipboard.writeText(text);
    showToast("คัดลอกแล้ว");
  } catch {
    showToast("คัดลอกไม่ได้ — เลือกข้อความแล้วกด Ctrl+C", true);
  }
}

async function _loadSceneInfo(projectId) {
  try {
    _sbScenesInfo = await (await fetch(`/api/project/${projectId}/scenes`)).json();
  } catch { _sbScenesInfo = []; }
}

function _sceneQuery(i) {
  const info = _sbScenesInfo[i];
  return info ? info.query : "";
}

async function _sbAiImage(idx) {
  const def = _sbQueries[idx] || (_sbScenes[idx] || "").slice(0, 80);
  const prompt = window.prompt("คำอธิบายภาพ (ภาษาอังกฤษจะได้ผลดีที่สุด):", def);
  if (!prompt) return;
  const thumb = document.querySelectorAll(".sb-scene")[idx]?.querySelector(".sb-thumb");
  if (thumb) thumb.innerHTML = '<div class="sb-no-media">🎨 กำลังสร้างภาพ...<br><small>ครั้งแรกโหลดโมเดล ~1 นาที</small></div>';
  try {
    const resp = await fetch(`/api/project/${_sbProjectId}/ai-image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, engine: selectedAiEngine }),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "สร้างภาพไม่สำเร็จ");
    while (_sbMediaFiles.length <= idx) _sbMediaFiles.push(null);
    if (_sbMediaFiles[idx]) _sbRemoved.push(_sbMediaFiles[idx]);
    _sbMediaFiles[idx] = { filename: data.filename, type: "image" };
    _markPreviewOutdated();
    showToast("ได้ภาพ AI แล้ว — ภาพเดิมอยู่ในรายการ 'เอาออกแล้ว'");
  } catch (e) {
    showToast(e.message, true);
  }
  _renderStoryboard();
}

// ── Stat cards (HyperFrames) ──

let selectedGraphics = "off";
let _graphicsAvailable = false;
let _cardSceneIdx = null;

function selectGraphics(val) {
  if (val === "on" && !_graphicsAvailable) {
    showToast("ไม่พบ Node.js 22+ หรือแม่แบบการ์ด — ใช้การ์ดตัวเลขไม่ได้", true);
    val = "off";
  }
  selectedGraphics = val;
  document.querySelectorAll("[data-graphics]").forEach((b) => b.classList.toggle("active", b.dataset.graphics === val));
}

async function loadGraphicsStatus() {
  try {
    _graphicsAvailable = (await (await fetch("/api/graphics/status")).json()).available;
  } catch { _graphicsAvailable = false; }
}

function openCardDialog(idx) {
  _cardSceneIdx = idx;
  const stat = (_sbScenesInfo[idx] || {}).stat || {};
  const fmt = (v) => (v === undefined || v === null || v === "") ? ""
    : Number(v).toLocaleString("en-US", { maximumFractionDigits: stat.decimals ?? 2 });
  document.getElementById("cardSceneNum").textContent = idx + 1;
  document.getElementById("cardValue").value = fmt(stat.value);
  document.getElementById("cardUnit").value = stat.unit || "";
  document.getElementById("cardLabel").value = stat.label || "";
  document.getElementById("cardBadge").value = stat.badge || "";
  document.getElementById("cardCaption").value = stat.caption || "";
  document.getElementById("cardMakeBtn").disabled = false;
  document.getElementById("cardModal").classList.remove("hidden");
  document.getElementById("cardValue").focus();
}

function closeCardDialog() {
  document.getElementById("cardModal").classList.add("hidden");
  _cardSceneIdx = null;
}

async function confirmCardDialog() {
  const idx = _cardSceneIdx;
  const get = (id) => document.getElementById(id).value.trim();
  const value = get("cardValue").replace(/,/g, "");
  if (idx === null || value === "" || isNaN(Number(value))) return showToast("ใส่ตัวเลขให้ถูกต้อง", true);
  const body = { index: idx, value, unit: get("cardUnit"), label: get("cardLabel"),
                 badge: get("cardBadge"), caption: get("cardCaption") };
  closeCardDialog();
  const thumb = document.querySelectorAll(".sb-scene")[idx]?.querySelector(".sb-thumb");
  if (thumb) thumb.innerHTML = '<div class="sb-no-media">📊 กำลังสร้างการ์ด...<br><small>ประมาณ 20 วินาที</small></div>';
  try {
    const resp = await fetch(`/api/project/${_sbProjectId}/graphic-card`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || "สร้างการ์ดไม่สำเร็จ");
    while (_sbMediaFiles.length <= idx) _sbMediaFiles.push(null);
    if (_sbMediaFiles[idx]) _sbRemoved.push(_sbMediaFiles[idx]);
    _sbMediaFiles[idx] = { filename: data.filename, type: "video" };
    _markPreviewOutdated();
    showToast("ได้การ์ดตัวเลขแล้ว — สื่อเดิมอยู่ในรายการ 'เอาออกแล้ว'");
  } catch (e) {
    showToast(e.message, true);
  }
  _renderStoryboard();
}

// ── Queue: many topics, one clip at a time, fully automatic ──

const QUEUE_LABELS = { waiting: "รอคิว", running: "กำลังทำ", needs_review: "รอตรวจ", done: "เสร็จแล้ว", error: "ล้มเหลว" };
let _queueTimer = null;
let _queuePaused = false;
let _queueHadWork = false;

async function _postQueue(topics) {
  const settings = _generateSettings("");
  delete settings.topic;
  const resp = await fetch("/api/queue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topics, settings }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || "เพิ่มเข้าคิวไม่ได้");
  return data.added;
}

async function addCurrentToQueue() {
  const topic = document.getElementById("topicInput").value.trim();
  if (!topic) return showToast("กรุณาใส่หัวข้อ", true);
  try {
    await _postQueue([topic]);
    showToast(`เพิ่ม "${topic}" เข้าคิวแล้ว (อัตโนมัติเต็ม)`);
    document.getElementById("topicInput").value = "";
    loadQueue();
  } catch (e) { showToast(e.message, true); }
}

async function addTopicsToQueue() {
  const box = document.getElementById("queueTopics");
  const topics = box.value.split("\n").map((t) => t.trim()).filter(Boolean);
  if (!topics.length) return showToast("ใส่หัวข้อบรรทัดละ 1 หัวข้อ", true);
  try {
    const added = await _postQueue(topics);
    box.value = "";
    showToast(`เพิ่มเข้าคิว ${added} หัวข้อ`);
    loadQueue();
  } catch (e) { showToast(e.message, true); }
}

async function _queueControl(action) {
  await fetch("/api/queue/control", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }),
  });
  loadQueue();
}

function toggleQueuePause() { _queueControl(_queuePaused ? "resume" : "pause"); }
function clearFinishedQueue() { _queueControl("clear_finished"); }

async function queueRetry(id) {
  await fetch(`/api/queue/${id}/retry`, { method: "POST" });
  loadQueue();
}

async function queueRemove(id) {
  await fetch(`/api/queue/${id}`, { method: "DELETE" });
  loadQueue();
}

async function loadQueue() {
  let q;
  try { q = await (await fetch("/api/queue")).json(); } catch { return; }
  _queuePaused = q.paused;
  const items = q.items || [];
  const section = document.getElementById("queueSection");
  const active = items.filter((i) => ["waiting", "running"].includes(i.status));
  section.classList.toggle("has-items", items.length > 0);
  document.getElementById("queuePauseBtn").textContent = q.paused ? "▶ ทำต่อ" : "⏸ หยุดชั่วคราว";
  const count = (s) => items.filter((i) => i.status === s).length;
  document.getElementById("queueSummary").textContent = items.length
    ? `รอ ${count("waiting")} · กำลังทำ ${count("running")} · เสร็จ ${count("done")} · รอตรวจ ${count("needs_review")} · ล้มเหลว ${count("error")}${q.paused ? " · หยุดชั่วคราว" : ""}`
    : "ยังไม่มีงานในคิว";
  document.getElementById("queueList").innerHTML = items.map((i) => {
    const progress = i.status === "running" && i.progress != null ? ` ${i.progress}%` : "";
    const open = i.project_id ? `<button class="tool-btn" onclick="loadProject('${i.project_id}')">เปิด</button>` : "";
    const retry = ["error", "needs_review"].includes(i.status) ? `<button class="tool-btn" onclick="queueRetry('${i.id}')">ทำใหม่</button>` : "";
    const remove = i.status !== "running" ? `<button class="tool-btn" onclick="queueRemove('${i.id}')" title="เอาออกจากคิว">✕</button>` : "";
    const err = i.error ? `<div class="queue-error">${escapeHtml(i.error)}</div>` : "";
    return `<div class="queue-item q-${i.status}">
      <div class="queue-main"><span class="queue-status">${QUEUE_LABELS[i.status] || i.status}${progress}</span>
        <span class="queue-topic">${escapeHtml(i.topic)}</span>${open}${retry}${remove}</div>${err}</div>`;
  }).join("");

  // Poll while there is work; chime once when the queue empties.
  if (active.length) _queueHadWork = true;
  else if (_queueHadWork) { _queueHadWork = false; playDoneSound(); showToast("คิวว่างแล้ว — ทำครบทุกหัวข้อ"); loadHistory(); }
  clearTimeout(_queueTimer);
  _queueTimer = setTimeout(loadQueue, active.length ? 3000 : 15000);
}

// ── Keep the page's state across refreshes / navigation ──
// Per-browser convenience only: settings, chosen media and the clip being
// worked on are restored when the dashboard is opened again.

const FORM_KEY = "yt.form.v1";
const PROJECT_KEY = "yt.project";
let _saveFormTimer = null;

function _storageGet(store, key) {
  try { return store.getItem(key); } catch { return null; }
}

function _storageSet(store, key, value) {
  try { store.setItem(key, value); } catch { /* private mode / storage full */ }
}

function _scheduleSaveForm() {
  clearTimeout(_saveFormTimer);
  _saveFormTimer = setTimeout(() => {
    const state = _collectFormState();
    state.media = selectedMedia;
    state.bgmName = document.getElementById("bgmFileName").textContent;
    state.presetId = document.getElementById("voicePresetSelect").value;
    _storageSet(localStorage, FORM_KEY, JSON.stringify(state));
  }, 400);
}

function _rememberProject(id) {
  if (id) _storageSet(sessionStorage, PROJECT_KEY, id);
}

function _restoreSavedForm() {
  let saved;
  try { saved = JSON.parse(_storageGet(localStorage, FORM_KEY) || "null"); } catch { saved = null; }
  if (!saved) return;
  _restoreFormState(saved);
  _currentDraftId = saved.id || null;
  if (Array.isArray(saved.media) && saved.media.length) {
    selectedMedia = saved.media;
    renderMediaGrid();
  }
  if (saved.bgmFile) {
    bgmFilename = saved.bgmFile;
    document.getElementById("bgmFileName").textContent = saved.bgmName || saved.bgmFile;
    document.getElementById("bgmPlayer").src = `/api/uploads/file/${bgmFilename}`;
    document.getElementById("bgmEmpty").classList.add("hidden");
    document.getElementById("bgmPreview").classList.remove("hidden");
  }
  if (saved.presetId && _voicePresets.some((p) => p.id === saved.presetId)) {
    document.getElementById("voicePresetSelect").value = saved.presetId;
    _showPresetInfo(saved.presetId);
  }
}

const setupPanel = document.getElementById("setupPanel");
["input", "change", "click"].forEach((ev) => setupPanel.addEventListener(ev, _scheduleSaveForm));

(async () => {
  await loadVoiceProfiles();
  await loadVoicePresets();
  await Promise.all([loadAiImageStatus(), loadGraphicsStatus()]);
  _restoreSavedForm();
  loadQueue();
  const linked = new URLSearchParams(location.search).get("project");
  const resumed = linked || _storageGet(sessionStorage, PROJECT_KEY);
  if (resumed) loadProject(resumed);
})();

// ── Version footer ──
const _THAI_MONTHS = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."];
function _thaiDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${_THAI_MONTHS[m - 1]} ${y + 543}`;
}
fetch("/api/version").then((r) => r.json()).then((v) => {
  document.getElementById("appVersion").textContent =
    `${v.name} v${v.version} · สร้าง ${_thaiDate(v.created)} · ปรับปรุงล่าสุด ${_thaiDate(v.updated)} · โดย ${v.author}`;
}).catch(() => {});
