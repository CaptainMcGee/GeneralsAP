/* Archipelago Cluster Placement Editor — Core 2D Canvas Editor */
"use strict";

// ── State ──────────────────────────────────────────────────────────────────────
const state = {
  registry: null,
  config: null,
  maps: {},            // map_id -> { version, map_id, clusters:[], ... }
  currentMapId: null,
  selectedIdx: -1,
  activeTier: "easy",
  zoom: 1.0,
  panX: 0, panY: 0,
  mapImage: null,
  mapImageLoading: false,
  show: { grid: false, labels: true, radii: true, waypoints: true },
  isDragging: false,
  dragIdx: -1,
  dragStartX: 0, dragStartY: 0,
  isPanning: false,
  panStartX: 0, panStartY: 0,
  panStartPanX: 0, panStartPanY: 0,
  undoStack: [],
  redoStack: [],
  seedMode: false,
  seedValue: 42,
  seedCount: 3,
  seedSelected: new Set(),
  dirty: new Set(),  // map IDs with unsaved changes
  nextClusterNum: {},
};

const TIER_COLORS = { easy: "#4CAF50", medium: "#FF9800", hard: "#F44336" };
const TIER_COLORS_DIM = { easy: "#2E7D32", medium: "#E65100", hard: "#B71C1C" };

// ── DOM refs ───────────────────────────────────────────────────────────────────
const canvas = document.getElementById("editor-canvas");
const ctx = canvas.getContext("2d");
const container = document.getElementById("canvas-container");

// ── API helpers ────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  return res.json();
}

// ── Init ───────────────────────────────────────────────────────────────────────
async function init() {
  state.registry = await api("GET", "/api/maps");
  state.config = await api("GET", "/api/config");

  // Build tabs
  const tabContainer = document.getElementById("map-tabs");
  for (const m of state.registry.maps) {
    const btn = document.createElement("button");
    btn.className = "map-tab";
    btn.dataset.mapId = m.id;
    btn.innerHTML = `${m.display_name} <span class="badge" id="badge-${m.id}">0</span>`;
    btn.addEventListener("click", () => switchMap(m.id));
    tabContainer.appendChild(btn);
  }

  // Load all map data
  for (const m of state.registry.maps) {
    state.maps[m.id] = await api("GET", `/api/clusters/${m.id}`);
    if (!state.maps[m.id].clusters) state.maps[m.id].clusters = [];
    updateBadge(m.id);
  }

  // Select first map
  if (state.registry.maps.length > 0) {
    switchMap(state.registry.maps[0].id);
  }

  // Canvas sizing
  resizeCanvas();
  window.addEventListener("resize", resizeCanvas);

  // Canvas events
  canvas.addEventListener("mousedown", onMouseDown);
  canvas.addEventListener("mousemove", onMouseMove);
  canvas.addEventListener("mouseup", onMouseUp);
  canvas.addEventListener("wheel", onWheel, { passive: false });
  canvas.addEventListener("contextmenu", e => e.preventDefault());

  // Toolbar
  document.getElementById("btn-grid").addEventListener("click", () => { state.show.grid = !state.show.grid; toggleBtnActive("btn-grid", state.show.grid); render(); });
  document.getElementById("btn-labels").addEventListener("click", () => { state.show.labels = !state.show.labels; toggleBtnActive("btn-labels", state.show.labels); render(); });
  document.getElementById("btn-radii").addEventListener("click", () => { state.show.radii = !state.show.radii; toggleBtnActive("btn-radii", state.show.radii); render(); });
  document.getElementById("btn-waypoints").addEventListener("click", () => { state.show.waypoints = !state.show.waypoints; toggleBtnActive("btn-waypoints", state.show.waypoints); render(); });
  document.getElementById("btn-recenter").addEventListener("click", recenter);
  document.getElementById("btn-seed").addEventListener("click", toggleSeedMode);

  // Tier buttons
  for (const btn of document.querySelectorAll(".tier-btn")) {
    btn.addEventListener("click", () => {
      state.activeTier = btn.dataset.tier;
      document.querySelectorAll(".tier-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  }

  // Action buttons
  document.getElementById("btn-save").addEventListener("click", saveCurrent);
  document.getElementById("btn-save-all").addEventListener("click", saveAll);
  document.getElementById("btn-export-map").addEventListener("click", exportCurrentMap);
  document.getElementById("btn-export-all").addEventListener("click", exportAll);
  document.getElementById("btn-import").addEventListener("click", importBundle);
  document.getElementById("btn-ini-preview").addEventListener("click", showIniPreview);
  document.getElementById("btn-undo").addEventListener("click", undo);
  document.getElementById("btn-redo").addEventListener("click", redo);

  // Seed panel
  document.getElementById("seed-close").addEventListener("click", toggleSeedMode);
  document.getElementById("seed-random").addEventListener("click", () => { document.getElementById("seed-input").value = Math.floor(Math.random() * 99999); updateSeedPreview(); });
  document.getElementById("seed-prev").addEventListener("click", () => { const el = document.getElementById("seed-input"); el.value = Math.max(0, +el.value - 1); updateSeedPreview(); });
  document.getElementById("seed-next").addEventListener("click", () => { const el = document.getElementById("seed-input"); el.value = +el.value + 1; updateSeedPreview(); });
  document.getElementById("seed-input").addEventListener("change", updateSeedPreview);
  document.getElementById("seed-count").addEventListener("change", updateSeedPreview);

  // Properties panel listeners
  for (const id of ["prop-id","prop-tier","prop-x","prop-y","prop-waypoint","prop-spread","prop-defend","prop-chase","prop-reserved","prop-notes"]) {
    const el = document.getElementById(id);
    if (el) el.addEventListener("change", onPropChange);
  }

  // Keyboard
  window.addEventListener("keydown", onKeyDown);

  // Initial active states
  toggleBtnActive("btn-labels", true);
  toggleBtnActive("btn-radii", true);
  toggleBtnActive("btn-waypoints", true);

  setStatus("Ready — click on map to place clusters");
  render();
}

// ── Map switching ──────────────────────────────────────────────────────────────
function switchMap(mapId) {
  state.currentMapId = mapId;
  state.selectedIdx = -1;
  state.undoStack = [];
  state.redoStack = [];

  // Update tab styles
  document.querySelectorAll(".map-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.mapId === mapId);
  });

  // Load map image
  loadMapImage(mapId);

  // Update waypoint dropdown
  updateWaypointDropdown();

  // Recenter
  setTimeout(recenter, 50);

  refreshClusterList();
  hideProps();
  render();

  if (state.seedMode) updateSeedPreview();
}

function loadMapImage(mapId) {
  const meta = getMapMeta(mapId);
  if (!meta) return;
  state.mapImage = null;
  state.mapImageLoading = true;
  const img = new Image();
  img.onload = () => { state.mapImage = img; state.mapImageLoading = false; recenter(); render(); };
  img.onerror = () => { state.mapImage = null; state.mapImageLoading = false; render(); };
  img.src = `maps/${meta.image}`;
}

function getMapMeta(mapId) {
  return state.registry?.maps?.find(m => m.id === mapId) || null;
}

function getClusters() {
  return state.maps[state.currentMapId]?.clusters || [];
}

// ── Canvas ─────────────────────────────────────────────────────────────────────
function resizeCanvas() {
  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
  render();
}

function worldToScreen(wx, wy) {
  return [wx * state.zoom + state.panX, wy * state.zoom + state.panY];
}

function screenToWorld(sx, sy) {
  return [(sx - state.panX) / state.zoom, (sy - state.panY) / state.zoom];
}

function recenter() {
  const meta = getMapMeta(state.currentMapId);
  if (!meta) return;
  const imgW = state.mapImage ? state.mapImage.width : meta.map_world_size[0];
  const imgH = state.mapImage ? state.mapImage.height : meta.map_world_size[1];
  const scaleX = canvas.width / imgW;
  const scaleY = canvas.height / imgH;
  state.zoom = Math.min(scaleX, scaleY) * 0.9;
  state.panX = (canvas.width - imgW * state.zoom) / 2;
  state.panY = (canvas.height - imgH * state.zoom) / 2;
  document.getElementById("zoom-display").textContent = `${Math.round(state.zoom * 100)}%`;
  render();
}

// ── Render ─────────────────────────────────────────────────────────────────────
function render() {
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Map image or placeholder
  if (state.mapImage) {
    const [sx, sy] = worldToScreen(0, 0);
    ctx.drawImage(state.mapImage, sx, sy, state.mapImage.width * state.zoom, state.mapImage.height * state.zoom);
  } else if (!state.mapImageLoading) {
    ctx.fillStyle = "#222";
    ctx.font = "14px sans-serif";
    ctx.textAlign = "center";
    const meta = getMapMeta(state.currentMapId);
    const name = meta ? meta.image : "map.png";
    ctx.fillText(`Drop ${name} into scripts/cluster_editor/maps/`, canvas.width / 2, canvas.height / 2);
    ctx.fillText("then refresh the page", canvas.width / 2, canvas.height / 2 + 20);
  }

  // Grid
  if (state.show.grid) drawGrid();

  // Waypoints
  if (state.show.waypoints) drawWaypoints();

  // Clusters
  const clusters = getClusters();
  for (let i = 0; i < clusters.length; i++) {
    drawCluster(clusters[i], i);
  }

  // Update 3D if available
  if (typeof update3D === "function") update3D();
}

function drawGrid() {
  const step = 100;
  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.lineWidth = 1;
  const meta = getMapMeta(state.currentMapId);
  const maxW = meta ? meta.map_world_size[0] : 2000;
  const maxH = meta ? meta.map_world_size[1] : 2000;
  for (let x = 0; x <= maxW; x += step) {
    const [sx] = worldToScreen(x, 0);
    const [, sy1] = worldToScreen(0, 0);
    const [, sy2] = worldToScreen(0, maxH);
    ctx.beginPath(); ctx.moveTo(sx, sy1); ctx.lineTo(sx, sy2); ctx.stroke();
  }
  for (let y = 0; y <= maxH; y += step) {
    const [sx1, sy] = worldToScreen(0, y);
    const [sx2] = worldToScreen(maxW, y);
    ctx.beginPath(); ctx.moveTo(sx1, sy); ctx.lineTo(sx2, sy); ctx.stroke();
  }
}

function drawWaypoints() {
  const meta = getMapMeta(state.currentMapId);
  if (!meta?.known_waypoints) return;
  for (const [name, [wx, wy]] of Object.entries(meta.known_waypoints)) {
    const [sx, sy] = worldToScreen(wx, wy);
    // Diamond marker
    ctx.fillStyle = "#00BCD4";
    ctx.beginPath();
    ctx.moveTo(sx, sy - 8); ctx.lineTo(sx + 6, sy); ctx.lineTo(sx, sy + 8); ctx.lineTo(sx - 6, sy);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 1;
    ctx.stroke();
    if (state.show.labels) {
      ctx.fillStyle = "#00BCD4";
      ctx.font = "10px monospace";
      ctx.textAlign = "center";
      ctx.fillText(name, sx, sy - 12);
    }
  }
}

function drawCluster(c, idx) {
  const [sx, sy] = worldToScreen(c.x, c.y);
  const tier = c.tier || "medium";
  const color = TIER_COLORS[tier];
  const isSelected = idx === state.selectedIdx;
  const isSeedDimmed = state.seedMode && !state.seedSelected.has(idx);
  const alpha = isSeedDimmed ? 0.2 : 1.0;

  // Radii circles
  if (state.show.radii) {
    const spread = (c.spread || 100) * state.zoom;
    const defend = (c.defend_radius || 375) * state.zoom;
    const chase = (c.chase_radius || 500) * state.zoom;

    // Chase radius (outer, dotted)
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = hexAlpha(color, 0.3 * alpha);
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(sx, sy, chase, 0, Math.PI * 2); ctx.stroke();

    // Defend radius (middle, dashed)
    ctx.setLineDash([8, 4]);
    ctx.strokeStyle = hexAlpha(color, 0.5 * alpha);
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(sx, sy, defend, 0, Math.PI * 2); ctx.stroke();

    // Spread radius (inner, solid)
    ctx.setLineDash([]);
    ctx.strokeStyle = hexAlpha(color, 0.8 * alpha);
    ctx.fillStyle = hexAlpha(color, 0.08 * alpha);
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(sx, sy, spread, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
  }

  ctx.setLineDash([]);

  // Center dot
  const r = isSelected ? 8 : 6;
  ctx.fillStyle = hexAlpha(color, alpha);
  ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.fill();
  if (isSelected) {
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.arc(sx, sy, r + 2, 0, Math.PI * 2); ctx.stroke();
  }

  // Label
  if (state.show.labels) {
    ctx.fillStyle = hexAlpha("#fff", alpha);
    ctx.font = `${isSelected ? "bold " : ""}11px monospace`;
    ctx.textAlign = "center";
    ctx.fillText(c.cluster_id || "?", sx, sy - r - 4);
  }
}

function hexAlpha(hex, a) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${a})`;
}

// ── Mouse events ───────────────────────────────────────────────────────────────
function onMouseDown(e) {
  const [wx, wy] = screenToWorld(e.offsetX, e.offsetY);

  // Right click or middle click = pan
  if (e.button === 1 || e.button === 2) {
    state.isPanning = true;
    state.panStartX = e.offsetX;
    state.panStartY = e.offsetY;
    state.panStartPanX = state.panX;
    state.panStartPanY = state.panY;
    canvas.style.cursor = "grabbing";
    return;
  }

  // Left click
  const clusters = getClusters();
  const hitIdx = findClusterAt(wx, wy);

  if (hitIdx >= 0) {
    // Click on existing cluster
    if (e.shiftKey) {
      // Delete
      pushUndo();
      clusters.splice(hitIdx, 1);
      markDirty();
      state.selectedIdx = -1;
      hideProps();
    } else {
      // Select and start drag
      state.selectedIdx = hitIdx;
      state.isDragging = true;
      state.dragIdx = hitIdx;
      state.dragStartX = wx;
      state.dragStartY = wy;
      showProps(hitIdx);
    }
  } else {
    // Place new cluster
    pushUndo();
    const meta = getMapMeta(state.currentMapId);
    const defaults = meta?.default_spreads || {};
    const regDefaults = state.registry || {};
    const newCluster = {
      cluster_id: makeClusterId(),
      tier: state.activeTier,
      x: Math.round(wx),
      y: Math.round(wy),
      waypoint_name: Object.keys(meta?.known_waypoints || {})[0] || "Player_1_Start",
      spread: defaults[state.activeTier] || 100,
      defend_radius: regDefaults.default_defend_radius || 375,
      chase_radius: regDefaults.default_chase_radius || 500,
      center_reserved_radius: regDefaults.default_center_reserved_radius || 0,
      notes: "",
    };
    clusters.push(newCluster);
    state.selectedIdx = clusters.length - 1;
    markDirty();
    showProps(state.selectedIdx);
  }
  refreshClusterList();
  render();
}

function onMouseMove(e) {
  const [wx, wy] = screenToWorld(e.offsetX, e.offsetY);

  // Coords display
  document.getElementById("coords-display").textContent = `Pixel: ${Math.round(wx)}, ${Math.round(wy)} | World: ${Math.round(wx)}, ${Math.round(wy)}`;

  if (state.isPanning) {
    state.panX = state.panStartPanX + (e.offsetX - state.panStartX);
    state.panY = state.panStartPanY + (e.offsetY - state.panStartY);
    render();
    return;
  }

  if (state.isDragging && state.dragIdx >= 0) {
    const clusters = getClusters();
    const c = clusters[state.dragIdx];
    if (c) {
      c.x = Math.round(wx);
      c.y = Math.round(wy);
      markDirty();
      if (state.dragIdx === state.selectedIdx) updatePropsDisplay();
      render();
      refreshClusterList();
    }
  }
}

function onMouseUp(e) {
  if (state.isPanning) {
    state.isPanning = false;
    canvas.style.cursor = "crosshair";
  }
  if (state.isDragging) {
    state.isDragging = false;
    state.dragIdx = -1;
  }
}

function onWheel(e) {
  e.preventDefault();
  const [wx, wy] = screenToWorld(e.offsetX, e.offsetY);
  const factor = e.deltaY < 0 ? 1.1 : 0.9;
  const newZoom = Math.max(0.1, Math.min(10, state.zoom * factor));
  // Zoom toward cursor position
  state.panX = e.offsetX - wx * newZoom;
  state.panY = e.offsetY - wy * newZoom;
  state.zoom = newZoom;
  document.getElementById("zoom-display").textContent = `${Math.round(state.zoom * 100)}%`;
  render();
}

function findClusterAt(wx, wy) {
  const clusters = getClusters();
  const hitRadius = 12 / state.zoom;
  for (let i = clusters.length - 1; i >= 0; i--) {
    const c = clusters[i];
    const dx = c.x - wx, dy = c.y - wy;
    if (dx * dx + dy * dy < hitRadius * hitRadius) return i;
  }
  return -1;
}

// ── Keyboard ───────────────────────────────────────────────────────────────────
function onKeyDown(e) {
  // Ignore if typing in input
  if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;

  if (e.key === "1") { setTier("easy"); }
  else if (e.key === "2") { setTier("medium"); }
  else if (e.key === "3") { setTier("hard"); }
  else if (e.key === "Delete" || e.key === "Backspace") { deleteSelected(); }
  else if (e.key === "g" || e.key === "G") { document.getElementById("btn-grid").click(); }
  else if (e.key === "l" || e.key === "L") { document.getElementById("btn-labels").click(); }
  else if (e.key === "r" || e.key === "R") { document.getElementById("btn-radii").click(); }
  else if (e.key === " ") { e.preventDefault(); recenter(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "z") { e.preventDefault(); undo(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "y") { e.preventDefault(); redo(); }
  else if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === "S") { e.preventDefault(); saveAll(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveCurrent(); }
  else if ((e.ctrlKey || e.metaKey) && e.key === "e") { e.preventDefault(); exportAll(); }
}

function setTier(tier) {
  state.activeTier = tier;
  document.querySelectorAll(".tier-btn").forEach(b => b.classList.toggle("active", b.dataset.tier === tier));
}

function deleteSelected() {
  if (state.selectedIdx < 0) return;
  pushUndo();
  getClusters().splice(state.selectedIdx, 1);
  state.selectedIdx = -1;
  markDirty();
  hideProps();
  refreshClusterList();
  render();
}

// ── Undo/Redo ──────────────────────────────────────────────────────────────────
function pushUndo() {
  state.undoStack.push(JSON.stringify(getClusters()));
  state.redoStack = [];
  if (state.undoStack.length > 50) state.undoStack.shift();
}

function undo() {
  if (state.undoStack.length === 0) return;
  state.redoStack.push(JSON.stringify(getClusters()));
  const prev = JSON.parse(state.undoStack.pop());
  state.maps[state.currentMapId].clusters = prev;
  state.selectedIdx = -1;
  markDirty();
  hideProps();
  refreshClusterList();
  render();
}

function redo() {
  if (state.redoStack.length === 0) return;
  state.undoStack.push(JSON.stringify(getClusters()));
  const next = JSON.parse(state.redoStack.pop());
  state.maps[state.currentMapId].clusters = next;
  state.selectedIdx = -1;
  markDirty();
  hideProps();
  refreshClusterList();
  render();
}

// ── Properties panel ───────────────────────────────────────────────────────────
function showProps(idx) {
  const panel = document.getElementById("props-panel");
  panel.style.display = "block";
  updatePropsDisplay();
}

function hideProps() {
  document.getElementById("props-panel").style.display = "none";
}

function updatePropsDisplay() {
  const c = getClusters()[state.selectedIdx];
  if (!c) return;
  document.getElementById("prop-id").value = c.cluster_id || "";
  document.getElementById("prop-tier").value = c.tier || "medium";
  document.getElementById("prop-x").value = c.x || 0;
  document.getElementById("prop-y").value = c.y || 0;
  document.getElementById("prop-spread").value = c.spread || 100;
  document.getElementById("prop-defend").value = c.defend_radius || 375;
  document.getElementById("prop-chase").value = c.chase_radius || 500;
  document.getElementById("prop-reserved").value = c.center_reserved_radius || 0;
  document.getElementById("prop-notes").value = c.notes || "";

  // Computed angle/distance from waypoint
  const meta = getMapMeta(state.currentMapId);
  const wpCoords = meta?.known_waypoints?.[c.waypoint_name];
  if (wpCoords) {
    const dx = c.x - wpCoords[0], dy = c.y - wpCoords[1];
    const angle = Math.atan2(dy, dx);
    const dist = Math.sqrt(dx * dx + dy * dy);
    document.getElementById("prop-angle").textContent = `${angle.toFixed(4)} rad (${(angle * 180 / Math.PI).toFixed(1)}°)`;
    document.getElementById("prop-distance").textContent = `${dist.toFixed(0)} units`;
  }

  // Waypoint dropdown
  const wpSelect = document.getElementById("prop-waypoint");
  wpSelect.value = c.waypoint_name || "";
}

function updateWaypointDropdown() {
  const meta = getMapMeta(state.currentMapId);
  const sel = document.getElementById("prop-waypoint");
  sel.innerHTML = "";
  if (meta?.known_waypoints) {
    for (const name of Object.keys(meta.known_waypoints)) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      sel.appendChild(opt);
    }
  }
  const custom = document.createElement("option");
  custom.value = "__custom__";
  custom.textContent = "(Custom...)";
  sel.appendChild(custom);
}

function onPropChange(e) {
  if (state.selectedIdx < 0) return;
  pushUndo();
  const c = getClusters()[state.selectedIdx];
  c.cluster_id = document.getElementById("prop-id").value;
  c.tier = document.getElementById("prop-tier").value;
  c.x = parseInt(document.getElementById("prop-x").value) || 0;
  c.y = parseInt(document.getElementById("prop-y").value) || 0;
  const wpVal = document.getElementById("prop-waypoint").value;
  if (wpVal === "__custom__") {
    const custom = prompt("Enter waypoint name:");
    if (custom) c.waypoint_name = custom;
  } else {
    c.waypoint_name = wpVal;
  }
  c.spread = parseInt(document.getElementById("prop-spread").value) || 100;
  c.defend_radius = parseInt(document.getElementById("prop-defend").value) || 375;
  c.chase_radius = parseInt(document.getElementById("prop-chase").value) || 500;
  c.center_reserved_radius = parseInt(document.getElementById("prop-reserved").value) || 0;
  c.notes = document.getElementById("prop-notes").value;
  markDirty();
  updatePropsDisplay();
  refreshClusterList();
  render();
}

// ── Cluster list ───────────────────────────────────────────────────────────────
function refreshClusterList() {
  const list = document.getElementById("cluster-list");
  list.innerHTML = "";
  const clusters = getClusters();
  document.getElementById("cluster-count").textContent = `(${clusters.length})`;
  updateBadge(state.currentMapId);

  for (let i = 0; i < clusters.length; i++) {
    const c = clusters[i];
    const div = document.createElement("div");
    div.className = `cluster-item ${i === state.selectedIdx ? "selected" : ""}`;
    div.innerHTML = `
      <span class="cluster-dot ${c.tier}"></span>
      <span class="cluster-info"><span class="id">${c.cluster_id}</span> <span class="coords">(${c.x}, ${c.y})</span></span>
      <button class="cluster-del" data-idx="${i}" title="Delete (Shift+Click)">&times;</button>
    `;
    div.addEventListener("click", (e) => {
      if (e.target.classList.contains("cluster-del")) {
        pushUndo();
        clusters.splice(i, 1);
        state.selectedIdx = -1;
        markDirty();
        hideProps();
        refreshClusterList();
        render();
        return;
      }
      state.selectedIdx = i;
      showProps(i);
      refreshClusterList();
      render();
    });
    list.appendChild(div);
  }
}

function updateBadge(mapId) {
  const badge = document.getElementById(`badge-${mapId}`);
  if (badge) {
    const count = (state.maps[mapId]?.clusters || []).length;
    badge.textContent = count;
  }
}

// ── Save/Load ──────────────────────────────────────────────────────────────────
async function saveCurrent() {
  const mapId = state.currentMapId;
  if (!mapId) return;
  await api("POST", `/api/clusters/${mapId}`, state.maps[mapId]);
  state.dirty.delete(mapId);
  setStatus(`Saved ${mapId} (${getClusters().length} clusters)`);
}

async function saveAll() {
  for (const mapId of Object.keys(state.maps)) {
    await api("POST", `/api/clusters/${mapId}`, state.maps[mapId]);
  }
  state.dirty.clear();
  setStatus("All maps saved");
}

function markDirty() {
  state.dirty.add(state.currentMapId);
}

// ── Export/Import ──────────────────────────────────────────────────────────────
async function exportCurrentMap() {
  const data = state.maps[state.currentMapId];
  downloadJSON(`${state.currentMapId}_clusters.json`, data);
}

async function exportAll() {
  const bundle = await api("GET", "/api/export");
  downloadJSON("archipelago_cluster_bundle.json", bundle);
}

function downloadJSON(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus(`Exported ${filename}`);
}

async function importBundle() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json";
  input.onchange = async () => {
    const file = input.files[0];
    if (!file) return;
    const text = await file.text();
    try {
      const data = JSON.parse(text);
      // Detect format: bundle or single map
      if (data.format === "archipelago_cluster_bundle" && data.maps) {
        const result = await api("POST", "/api/import", data);
        // Reload all imported maps
        for (const mid of (result.imported || [])) {
          state.maps[mid] = await api("GET", `/api/clusters/${mid}`);
          if (!state.maps[mid].clusters) state.maps[mid].clusters = [];
          updateBadge(mid);
        }
        setStatus(`Imported ${(result.imported || []).length} maps`);
      } else if (data.clusters && data.map_id) {
        // Single map
        state.maps[data.map_id] = data;
        await api("POST", `/api/clusters/${data.map_id}`, data);
        updateBadge(data.map_id);
        setStatus(`Imported ${data.map_id}`);
      } else {
        setStatus("Unknown import format");
      }
      refreshClusterList();
      render();
    } catch (err) {
      setStatus(`Import error: ${err.message}`);
    }
  };
  input.click();
}

async function showIniPreview() {
  const res = await fetch(`/api/ini-preview/${state.currentMapId}`);
  const text = await res.text();
  showModal("INI Preview — " + state.currentMapId, `<pre>${escHtml(text)}</pre>`, [
    { label: "Copy", action: () => { navigator.clipboard.writeText(text); setStatus("Copied to clipboard"); } },
    { label: "Close" },
  ]);
}

// ── Seed Preview ───────────────────────────────────────────────────────────────
function toggleSeedMode() {
  state.seedMode = !state.seedMode;
  document.getElementById("seed-panel").classList.toggle("visible", state.seedMode);
  toggleBtnActive("btn-seed", state.seedMode);
  if (state.seedMode) updateSeedPreview();
  render();
}

function updateSeedPreview() {
  state.seedValue = parseInt(document.getElementById("seed-input").value) || 0;
  state.seedCount = parseInt(document.getElementById("seed-count").value) || 3;
  const clusters = getClusters();
  state.seedSelected.clear();
  if (clusters.length <= state.seedCount) {
    // All selected
    for (let i = 0; i < clusters.length; i++) state.seedSelected.add(i);
  } else {
    // Deterministic selection using seed (same algorithm as Python)
    const indices = Array.from({ length: clusters.length }, (_, i) => i);
    let seed = state.seedValue;
    // Simple seeded shuffle (LCG)
    const rng = () => { seed = (seed * 1664525 + 1013904223) & 0xFFFFFFFF; return (seed >>> 0) / 4294967296; };
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    for (let i = 0; i < state.seedCount; i++) state.seedSelected.add(indices[i]);
  }
  document.getElementById("seed-info").textContent = `${state.seedSelected.size}/${clusters.length} clusters selected`;
  render();
}

// ── Cluster ID generation ──────────────────────────────────────────────────────
function makeClusterId() {
  const mapId = state.currentMapId;
  // Extract a short prefix from map ID (e.g., GC_TankGeneral -> TG)
  const prefix = mapId.replace("GC_", "").replace("General", "").substring(0, 4);
  const tierShort = { easy: "E", medium: "M", hard: "H" }[state.activeTier] || "M";
  if (!state.nextClusterNum[mapId]) {
    const clusters = getClusters();
    let max = 0;
    for (const c of clusters) {
      const match = c.cluster_id?.match(/_(\d+)$/);
      if (match) max = Math.max(max, parseInt(match[1]));
    }
    state.nextClusterNum[mapId] = max;
  }
  state.nextClusterNum[mapId]++;
  return `${prefix}_${tierShort}_${state.nextClusterNum[mapId]}`;
}

// ── Utilities ──────────────────────────────────────────────────────────────────
function toggleBtnActive(id, active) {
  document.getElementById(id).classList.toggle("active", active);
}

function setStatus(msg) {
  document.getElementById("status").textContent = msg;
}

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showModal(title, bodyHtml, buttons) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.innerHTML = `<h2>${escHtml(title)}</h2>${bodyHtml}<div class="modal-buttons"></div>`;
  const btnContainer = modal.querySelector(".modal-buttons");
  for (const b of (buttons || [{ label: "Close" }])) {
    const btn = document.createElement("button");
    btn.textContent = b.label;
    btn.addEventListener("click", () => { if (b.action) b.action(); backdrop.remove(); });
    btnContainer.appendChild(btn);
  }
  backdrop.appendChild(modal);
  backdrop.addEventListener("click", e => { if (e.target === backdrop) backdrop.remove(); });
  document.body.appendChild(backdrop);
}

// ── Start ──────────────────────────────────────────────────────────────────────
canvas.style.cursor = "crosshair";
init();
