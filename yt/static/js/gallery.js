let _items = [];
let _view = [];
let _ratioFilter = "all";
let _openIndex = -1;

const RATIO_LABELS = { "9:16": "แนวตั้ง 9:16", "16:9": "แนวนอน 16:9" };
const VOICE_LABELS = { female: "หญิง (เปรมวดี)", male: "ชาย (นิวัตน์)" };
const voiceLabel = (v) => VOICE_LABELS[v] || v;

function escapeHtml(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}

function fmtDuration(sec) {
  const s = Math.round(sec || 0);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function fmtTotal(sec) {
  const m = Math.round(sec / 60);
  return m >= 60 ? `${Math.floor(m / 60)} ชม. ${m % 60} นาที` : `${m} นาที`;
}

function fmtDate(ts) {
  if (!ts) return "";
  return new Date(ts * 1000).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short" });
}

function fmtSize(bytes) {
  return bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${(bytes / 1e6).toFixed(1)} MB`;
}

function thumbUrl(item, ratio) {
  return `/api/gallery/thumb/${item.project_id}?ratio=${encodeURIComponent(ratio)}&v=${item.updated_at || 0}`;
}

function videoUrl(item, ratio) {
  return `/api/download/${item.project_id}?ratio=${encodeURIComponent(ratio)}&v=${item.updated_at || 0}`;
}

function applyFilters() {
  const q = document.getElementById("gSearch").value.trim().toLowerCase();
  const sort = document.getElementById("gSort").value;
  _view = _items.filter((it) =>
    (!q || it.topic.toLowerCase().includes(q)) &&
    (_ratioFilter === "all" || it.ratios.includes(_ratioFilter)));
  const by = {
    newest: (a, b) => b.created_at - a.created_at,
    oldest: (a, b) => a.created_at - b.created_at,
    longest: (a, b) => b.duration - a.duration,
    shortest: (a, b) => a.duration - b.duration,
  }[sort];
  _view.sort(by);
  render();
}

function render() {
  const grid = document.getElementById("galleryGrid");
  grid.innerHTML = _view.map((it, i) => {
    const ratio = _ratioFilter !== "all" ? _ratioFilter : it.ratios[0];
    const badges = it.ratios.map((r) => `<span class="g-badge">${r}</span>`).join("");
    return `<button class="g-card" data-index="${i}" title="${escapeHtml(it.topic)}">
      <div class="g-thumb${ratio === "16:9" ? " landscape" : ""}">
        <img src="${thumbUrl(it, ratio)}" alt="" loading="lazy">
        <div class="g-badges">${badges}</div>
        <span class="g-duration">${fmtDuration(it.duration)}</span>
        <span class="g-play">&#9654;</span>
      </div>
      <div class="g-info">
        <div class="g-topic">${escapeHtml(it.topic)}</div>
        <div class="g-meta">${fmtDate(it.created_at)}${it.voice ? " · " + escapeHtml(voiceLabel(it.voice)) : ""}</div>
      </div>
    </button>`;
  }).join("");
  document.getElementById("galleryEmpty").classList.toggle("hidden", _view.length > 0);
}

function openPlayer(index, ratio) {
  if (index < 0 || index >= _view.length) return;
  _openIndex = index;
  const it = _view[index];
  const current = ratio || (_ratioFilter !== "all" && it.ratios.includes(_ratioFilter) ? _ratioFilter : it.ratios[0]);

  document.getElementById("gpTitle").textContent = it.topic;
  const video = document.getElementById("gpVideo");
  video.src = videoUrl(it, current);
  video.classList.toggle("landscape", current === "16:9");

  document.getElementById("gpRatios").innerHTML = it.ratios.length > 1
    ? it.ratios.map((r) => `<button class="ratio-tab${r === current ? " active" : ""}" data-ratio="${r}">${RATIO_LABELS[r] || r}</button>`).join("")
    : "";
  document.getElementById("gpMeta").textContent =
    `${fmtDate(it.created_at)} · ${fmtDuration(it.duration)} · ${fmtSize(it.size)}${it.voice ? " · เสียง: " + voiceLabel(it.voice) : ""}`;
  document.getElementById("gpDownloads").innerHTML = it.ratios.map((r) =>
    `<a class="download-btn" href="${videoUrl(it, r)}" download="${it.project_id}_${r.replace(":", "x")}.mp4">&#11015; ${RATIO_LABELS[r] || r}</a>`
  ).join("");
  document.getElementById("gpOpen").href = `/?project=${it.project_id}`;
  document.getElementById("gpPrev").disabled = index === 0;
  document.getElementById("gpNext").disabled = index === _view.length - 1;
  document.getElementById("playerModal").classList.remove("hidden");
}

function closePlayer() {
  const video = document.getElementById("gpVideo");
  video.pause();
  video.removeAttribute("src");
  video.load();
  document.getElementById("playerModal").classList.add("hidden");
  _openIndex = -1;
}

async function loadGallery() {
  try {
    const resp = await fetch("/api/gallery");
    _items = await resp.json();
  } catch {
    document.getElementById("galleryStats").textContent = "โหลดไม่สำเร็จ — เซิร์ฟเวอร์ทำงานอยู่หรือไม่?";
    return;
  }
  const total = _items.reduce((s, it) => s + (it.duration || 0), 0);
  document.getElementById("galleryStats").textContent = `${_items.length} คลิป · รวม ${fmtTotal(total)}`;
  applyFilters();
}

document.getElementById("gSearch").addEventListener("input", applyFilters);
document.getElementById("gSort").addEventListener("change", applyFilters);
document.getElementById("gRatio").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-ratio]");
  if (!btn) return;
  _ratioFilter = btn.dataset.ratio;
  document.querySelectorAll("#gRatio .voice-btn").forEach((b) => b.classList.toggle("active", b === btn));
  applyFilters();
});
document.getElementById("galleryGrid").addEventListener("click", (e) => {
  const card = e.target.closest(".g-card");
  if (card) openPlayer(Number(card.dataset.index));
});
document.getElementById("gpRatios").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-ratio]");
  if (btn) openPlayer(_openIndex, btn.dataset.ratio);
});
document.getElementById("gpClose").addEventListener("click", closePlayer);
document.getElementById("gpPrev").addEventListener("click", () => openPlayer(_openIndex - 1));
document.getElementById("gpNext").addEventListener("click", () => openPlayer(_openIndex + 1));
document.getElementById("playerModal").addEventListener("click", (e) => {
  if (e.target.id === "playerModal") closePlayer();
});
document.addEventListener("keydown", (e) => {
  if (_openIndex < 0) return;
  if (e.key === "Escape") closePlayer();
  else if (e.target.tagName === "VIDEO") return;
  else if (e.key === "ArrowLeft") openPlayer(_openIndex - 1);
  else if (e.key === "ArrowRight") openPlayer(_openIndex + 1);
});

// Opened from the dashboard (named tab): go back to that tab instead of
// loading a fresh dashboard, so its unsaved work stays as it was.
function _dashboard() {
  try {
    return window.opener && !window.opener.closed && window.opener.location.pathname === "/"
      ? window.opener : null;
  } catch { return null; }
}

document.getElementById("backLink").addEventListener("click", (e) => {
  const dash = _dashboard();
  if (!dash) return;
  e.preventDefault();
  dash.focus();
  window.close();
});

document.getElementById("gpOpen").addEventListener("click", (e) => {
  const dash = _dashboard();
  if (!dash || _openIndex < 0) return;
  e.preventDefault();
  dash.loadProject(_view[_openIndex].project_id);
  dash.focus();
  closePlayer();
});

loadGallery();

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
