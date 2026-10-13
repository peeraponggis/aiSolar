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
let selectedDuration = "short";
let selectedTTSEngine = "edge-tts";
let selectedCloneEngine = "openvoice";
let ttsEnginesData = null;
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
  media_ready: "จัดเรียง media แล้วกดสร้างวิดีโอ",
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

async function loadTTSEngines() {
  try {
    const resp = await fetch("/api/tts-engines");
    if (!resp.ok) return;
    ttsEnginesData = await resp.json();
    const sel = document.getElementById("ttsEngineSelect");
    const cloneSel = document.getElementById("cloneEngineSelect");
    sel.innerHTML = "";
    cloneSel.innerHTML = "";
    for (const eng of ttsEnginesData.engines) {
      const opt = document.createElement("option");
      opt.value = eng.name;
      opt.textContent = eng.label + (eng.available ? "" : " (ไม่ได้ติดตั้ง)");
      opt.disabled = !eng.available;
      sel.appendChild(opt);
    }
    for (const eng of ttsEnginesData.clone_engines) {
      const opt = document.createElement("option");
      opt.value = eng.name;
      opt.textContent = eng.label + (eng.available ? "" : " (ไม่ได้ติดตั้ง)");
      opt.disabled = !eng.available;
      cloneSel.appendChild(opt);
    }
    sel.value = selectedTTSEngine;
    cloneSel.value = selectedCloneEngine;
  } catch {}
}

function onTTSEngineChange(engineName) {
  selectedTTSEngine = engineName;
  if (!ttsEnginesData) return;
  const eng = ttsEnginesData.engines.find(e => e.name === engineName);
  if (!eng || !eng.voices.length) return;
  const container = document.getElementById("voiceToggle");
  container.innerHTML = "";
  eng.voices.forEach((v, i) => {
    const btn = document.createElement("button");
    btn.className = "voice-btn" + (i === 0 ? " active" : "");
    btn.dataset.voice = v.id;
    btn.textContent = v.name;
    btn.onclick = () => selectVoice(v.id);
    container.appendChild(btn);
  });
  selectedVoice = eng.voices[0].id;
  if (selectedMode === "dialogue") {
    const bContainer = document.querySelector("[data-voiceb]")?.parentElement;
    if (bContainer && eng.voices.length > 1) {
      bContainer.innerHTML = "";
      eng.voices.forEach((v, i) => {
        const btn = document.createElement("button");
        btn.className = "voice-btn" + ((i === 1 || (eng.voices.length === 1 && i === 0)) ? " active" : "");
        btn.dataset.voiceb = v.id;
        btn.textContent = v.name;
        btn.onclick = () => selectVoiceB(v.id);
        bContainer.appendChild(btn);
      });
      selectedVoiceB = eng.voices.length > 1 ? eng.voices[1].id : eng.voices[0].id;
    }
  }
}

function onCloneEngineChange(engineName) {
  selectedCloneEngine = engineName;
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
      tts_engine: selectedTTSEngine,
    });
    if (selectedTone === "custom") {
      params.set("tone_rate", document.getElementById("customToneRate").value || "0");
      params.set("tone_pitch", document.getElementById("customTonePitch").value || "0");
    }
    if (cloneVoiceId) {
      params.set("clone_voice_id", cloneVoiceId);
      params.set("clone_tau", document.getElementById("tauSlider")?.value || "30");
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
  const scriptInput = document.getElementById("customScriptInput");
  const selStart = scriptInput.selectionStart;
  const selEnd = scriptInput.selectionEnd;
  const selected = selEnd > selStart
    ? scriptInput.value.substring(selStart, selEnd).trim()
    : "";
  const customScript = selected || scriptInput.value.trim();
  if (selected) {
    showToast(`ใช้เฉพาะส่วนที่ไฮไลท์ (${selected.length} ตัวอักษร)`);
  }

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
    tts_engine: selectedTTSEngine,
    clone_engine: selectedCloneEngine,
  });
  if (selectedMedia.length) {
    params.set("media_files", selectedMedia.map((m) => m.filename).join(","));
    const durations = selectedMedia.map((m) => m.displayDuration || 0);
    if (durations.some((d) => d > 0)) {
      params.set("media_durations", durations.join(","));
    }
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

      if (data.phase === "media_ready") {
        clearInterval(pollTimer);
        pollTimer = null;
        setTimeout(pollLogs, 500);
        updateEta(0);
        showStoryboardPreview(data);
        showToast("จัดเรียง media แล้วกด สร้างวิดีโอ");
      } else if (data.phase === "done") {
        clearInterval(pollTimer);
        setTimeout(pollLogs, 500);
        updateEta(100);
        showResult(data);
        resetButton();
        showToast("สร้างคลิปเสร็จแล้ว ค่ะ");
        playDoneSound();
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

  switchTab("storyboard");
  buildStoryboard(data);
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
let _sbPhase = null;
let _sbDragIdx = null;

function showStoryboardPreview(data) {
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

  _sbPhase = "media_ready";
  switchTab("storyboard");
  buildStoryboard(data);
}

async function _startRender() {
  if (!currentProjectId) return;
  const btn = document.querySelector(".sb-render-btn");
  if (btn) { btn.disabled = true; btn.textContent = "กำลังสร้าง..."; }
  _sbPhase = "rendering";

  const body = {};
  const scriptText = _sbScenes.filter((s) => s.trim()).join("\n\n");
  if (scriptText) body.script = scriptText;
  if (_sbDurations.some((d) => d > 0)) body.media_durations = _sbDurations;
  if (_sbMediaFiles.length) {
    body.media_order = _sbMediaFiles.filter(Boolean).map((m) => m.filename);
  }

  try {
    const resp = await fetch(`/api/project/${currentProjectId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error("render start failed");
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

  _sbProjectId = data.project_id;
  _sbScenes = data.script
    .split(/\n\s*\n/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);

  try {
    const resp = await fetch(`/api/project/${data.project_id}/media`);
    if (resp.ok) _sbMediaFiles = await resp.json();
  } catch {}

  const n = Math.max(_sbScenes.length, _sbMediaFiles.length);
  _sbDurations = new Array(n).fill(0);

  _renderStoryboard(data);
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
  return `<div class="sb-warning"><span>⚠</span><span>${_escapeHtml(msg)}</span></div>`;
}

function _renderStoryboard(data) {
  const container = document.getElementById("storyboardTimeline");
  const pid = _sbProjectId;

  const videoUrl = data && data.video_paths
    ? `/api/download/${pid}?ratio=${encodeURIComponent(Object.keys(data.video_paths)[0] || "9:16")}`
    : data && data.video_path
      ? `/api/download/${pid}`
      : null;

  let html = "";

  if (videoUrl) {
    html += `<div class="sb-player">
      <video controls preload="metadata"><source src="${videoUrl}" type="video/mp4"></video>
    </div>`;
  }

  const editable = _sbPhase === "media_ready";

  if (editable) {
    html += _sbMismatchWarning();
    html += `<div class="sb-render-bar">
      <span>ลากที่ ≡ เพื่อสลับลำดับ · คลิกรูปเพื่อเปลี่ยนสื่อ · แก้ข้อความเปลี่ยนเฉพาะซับไตเติ้ล (ไม่เปลี่ยนเสียง)</span>
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
          oninput="_sbEditScript(${i},this.value)">${_escapeHtml(text)}</textarea>
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
        ? `<div class="sb-text">${_escapeHtml(truncated)}</div>`
        : '<div class="sb-extra-label">(ไม่มีข้อความ)</div>';
    }

    const dragAttrs = editable
      ? `draggable="true" ondragstart="_sbDragStart(event,${i})" ondragover="_sbDragOver(event,${i})" ondrop="_sbDrop(event,${i})" ondragend="_sbDragEnd(event)"`
      : "";

    html += `<div class="sb-scene" ${dragAttrs}>
      ${editable ? '<div class="sb-drag-handle" title="ลากเพื่อสลับลำดับ">≡</div>' : ""}
      <div class="sb-scene-num">${sceneNum}</div>
      <div class="sb-thumb" onclick="openMediaPicker(${i},'${fname}')" title="คลิกเพื่อเปลี่ยนสื่อ">${thumbContent}</div>
      <div class="sb-body">${bodyHtml}</div>
    </div>`;
  }
  html += "</div>";

  container.innerHTML = html;
}

function _sbEditScript(idx, text) {
  while (_sbScenes.length <= idx) _sbScenes.push("");
  _sbScenes[idx] = text;
}

function _sbEditDuration(idx, val) {
  while (_sbDurations.length <= idx) _sbDurations.push(0);
  _sbDurations[idx] = parseFloat(val) || 0;
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

  _renderStoryboard(null);
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
  for (const m of _sbMediaFiles) {
    const src = `/api/project/${_sbProjectId}/media/${m.filename}`;
    const active = m.filename === currentFilename ? " sb-pick-active" : "";
    const tag = m.type === "video"
      ? `<video src="${src}" preload="metadata" muted></video>`
      : `<img src="${src}" loading="lazy">`;
    grid += `<div class="sb-pick-item${active}" data-fname="${_escapeAttr(m.filename)}">
      ${tag}<span>${_escapeHtml(m.filename)}</span>
    </div>`;
  }

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

  const targetIdx = _sbMediaFiles.findIndex((m) => m && m.filename === targetFname);
  if (targetIdx < 0) return;

  const tmp = _sbMediaFiles[sceneIdx];
  _sbMediaFiles[sceneIdx] = _sbMediaFiles[targetIdx];
  _sbMediaFiles[targetIdx] = tmp;

  _renderStoryboard(null);
}

function _escapeAttr(str) {
  return str.replace(/&/g, "&amp;").replace(/'/g, "&#39;").replace(/"/g, "&quot;");
}

function _escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

// ── Drafts ──

let _currentDraftId = null;

function _collectFormState() {
  return {
    id: _currentDraftId,
    topic: document.getElementById("topicInput").value.trim(),
    voice: selectedVoice,
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
    ttsEngine: selectedTTSEngine,
    cloneEngine: selectedCloneEngine,
  };
}

function _restoreFormState(d) {
  document.getElementById("topicInput").value = d.topic || "";
  if (d.voice) selectVoice(d.voice);
  if (d.tone) { document.getElementById("toneSelect").value = d.tone; selectTone(d.tone); }
  if (d.subtitles !== undefined) toggleSubtitles(d.subtitles ? "on" : "off");
  if (d.persona) { document.getElementById("personaInput").value = d.persona; document.getElementById("personaInput")._userEdited = true; }
  if (d.customScript) document.getElementById("customScriptInput").value = d.customScript;
  if (d.bgmVolume) document.getElementById("bgmVolumeSlider").value = d.bgmVolume;
  if (d.aspectRatios) {
    selectedAspectRatios = d.aspectRatios;
    document.querySelectorAll("[data-ratio]").forEach(b => b.classList.toggle("active", selectedAspectRatios.includes(b.dataset.ratio)));
  }
  if (d.mode) { selectedMode = d.mode; document.querySelectorAll("[data-mode]").forEach(b => b.classList.toggle("active", b.dataset.mode === d.mode)); }
  if (d.voiceB) selectVoiceB(d.voiceB);
  if (d.duration) { selectedDuration = d.duration; document.querySelectorAll("[data-dur]").forEach(b => b.classList.toggle("active", b.dataset.dur === d.duration)); }
  if (d.cloneTau) document.getElementById("tauSlider").value = d.cloneTau;
  if (d.overlayText) { const el = document.getElementById("overlayTextInput"); if (el) el.value = d.overlayText; }
  if (d.overlayFont) { const el = document.getElementById("overlayFont"); if (el) el.value = d.overlayFont; }
  if (d.overlayAnimation) { const el = document.getElementById("overlayAnimation"); if (el) el.value = d.overlayAnimation; }
  if (d.ttsEngine) { selectedTTSEngine = d.ttsEngine; document.getElementById("ttsEngineSelect").value = d.ttsEngine; onTTSEngineChange(d.ttsEngine); }
  if (d.cloneEngine) { selectedCloneEngine = d.cloneEngine; document.getElementById("cloneEngineSelect").value = d.cloneEngine; }
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
  const tauRow = document.getElementById("cloneTauRow");
  if (voiceId) {
    info.classList.remove("hidden");
    tauRow.classList.remove("hidden");
    const sel = document.getElementById("cloneVoiceSelect");
    const opt = sel.options[sel.selectedIndex];
    document.getElementById("cloneVoiceName").textContent = opt.text;
    document.getElementById("clonePreview").src = `/api/voices/${voiceId}/preview`;
  } else {
    info.classList.add("hidden");
    tauRow.classList.add("hidden");
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
  tts_engine: {
    title: "TTS Engine (ระบบสังเคราะห์เสียง)",
    body: "เลือกระบบสร้างเสียงพูด:\n\n<b>edge-tts (Microsoft)</b> — เสียงคุณภาพสูง ต้องมีอินเทอร์เน็ต (ค่าเริ่มต้น)\n\n<b>PyThaiTTS (VachanaTTS)</b> — โมเดล VITS ออฟไลน์ มี 4 เสียง\nติดตั้ง: pip install pythaitts\nLicense: Apache 2.0\n\n<b>Piper TTS</b> — ONNX runtime เร็วมาก ต้องดาวน์โหลด voice model\nติดตั้ง: pip install piper-tts\nวาง voice model ไว้ที่ models/piper/\n\n<b>MOSS-TTS Nano</b> — โมเดล 100M พารามิเตอร์ ต้องมี reference clip\nติดตั้ง: git clone + pip install -e .\nต้องการ GPU\n\nengine ที่ยังไม่ได้ติดตั้งจะแสดงเป็นสีเทา"
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
    body: "ใช้ AI โคลนน้ำเสียงจากไฟล์เสียงที่อัปโหลด\n\n<b>เลือก Clone Engine:</b>\n\n<b>OpenVoice V2</b> — สร้างเสียง TTS ก่อน แล้วแปลงน้ำเสียง (2 ขั้นตอน)\nใช้ .venv-clone (Python 3.12 + torch)\n\n<b>F5-TTS-THAI</b> — สร้างเสียงจาก reference โดยตรง (1 ขั้นตอน)\nใช้ .venv-f5 แยกต่างหาก (เพราะ numpy ชนกับ OpenVoice)\nต้องการ GPU — ระบบจะตัด reference ให้เหลือ 8 วินาทีอัตโนมัติ\n\n<b>ติดตั้ง F5-TTS-THAI:</b>\npython -m venv .venv-f5\n.venv-f5\\Scripts\\python -m pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124\n.venv-f5\\Scripts\\python -m pip install --only-binary=:all: numpy==1.26.4 scikit-learn==1.6.1\n.venv-f5\\Scripts\\python -m pip install git+https://github.com/VYNCX/F5-TTS-THAI.git\n.venv-f5\\Scripts\\python -m pip install pyarrow==17.0.0 datasets==2.21.0\n.venv-f5\\Scripts\\python -m pip uninstall -y torchcodec\n(สองบรรทัดสุดท้ายแก้ conflict ภายในแพ็กเกจ F5 เอง — pyarrow ใหม่ต้องการ numpy 2, torchcodec ชน DLL กับ torch 2.6)\n\n<b>วิธีใช้:</b>\n1. เลือก Clone Engine\n2. กด \"+ อัปโหลดเสียง\" เลือกไฟล์เสียงพูดชัดๆ 5-30 วินาที\n3. ตั้งชื่อเสียง แล้วเลือกจาก dropdown\n\n<b>ไม่ใช้</b> = ใช้เสียง TTS ปกติ"
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
loadTTSEngines();
