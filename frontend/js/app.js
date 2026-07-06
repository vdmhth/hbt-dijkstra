const SAMPLE_POINTS = [
  { name: "Pair 1 · N → S", src: [21.0110, 105.8492], dst: [20.9962, 105.8512] },
  { name: "Pair 2 · W → E", src: [21.0005, 105.8425], dst: [21.0020, 105.8585] },
  { name: "Pair 3 · diagonal", src: [20.9952, 105.8432], dst: [21.0102, 105.8580] },
]; // this is for quick demonstration 
let LANDMARKS = [];
const LANDMARKS_FALLBACK = [
  { name: "HUST", lat: 21.0044, lon: 105.8455 },
  { name: "Bach Mai Hospital", lat: 21.0005, lon: 105.8416 },
  { name: "Thong Nhat Park", lat: 21.0171, lon: 105.8430 },
  { name: "NEU", lat: 20.9986, lon: 105.8450 },
  { name: "Tuoi Tre Park", lat: 21.0086, lon: 105.8556 },
  { name: "Vincom Ba Trieu", lat: 21.0118, lon: 105.8490 },
  { name: "Hom Market", lat: 21.0145, lon: 105.8530 },
  { name: "Mo Market", lat: 21.0019, lon: 105.8536 },
  { name: "Times City", lat: 20.9966, lon: 105.8665 },
  { name: "National Eye Hospital", lat: 21.0098, lon: 105.8488 },
]; // this is for fallback if the api fails to load the landmarks 

const state = { src: null, dst: null, nextPick: "src", lastRouteCoords: null, lastRoutePath: null };

const POI_TYPE_LABELS = {
  hospital: "Hospital", university: "University", college: "College",
  marketplace: "Market", mall: "Mall", park: "Park",
  fuel: "Fuel", atm: "ATM", cafe: "Cafe", pharmacy: "Pharmacy", bank: "Bank", restaurant: "Restaurant",
};
const LANDMARK_TYPES = new Set(["hospital", "university", "college", "marketplace", "mall", "park"]);
let lastPois = []; // POIs currently drawn, for row-click panning

const $ = (id) => document.getElementById(id);

function setStatus(msg, kind = "") {
  const el = $("status");
  el.textContent = msg;
  el.className = "status" + (kind ? " " + kind : "");
}

function refreshRouteButton() {
  $("btn-route").disabled = !(state.src && state.dst);
} // ensure 2 points are chosen before routing
function applyStart(lat, lon) {
  state.src = [lat, lon];
  $("src-lat").value = lat.toFixed(6);
  $("src-lon").value = lon.toFixed(6);
  MapView.setStart(lat, lon);
  refreshRouteButton();
}
function applyEnd(lat, lon) {
  state.dst = [lat, lon];
  $("dst-lat").value = lat.toFixed(6);
  $("dst-lon").value = lon.toFixed(6);
  MapView.setEnd(lat, lon);
  refreshRouteButton();
}

async function setLandmarkEndpoint(which, lat, lon) {
  let snap;
  try {
    snap = await Api.nearest(lat, lon, currentSnapMode());
  } catch (err) {
    setStatus(err.message, "err");
    return;
  }
  if (!snap.ok) {
    setStatus(`Landmark is ${Math.round(snap.distance_m)} m from nearest road — outside network.`, "err");
    return;
  }
  MapView.clearRoute();
  MapView.clearPois();
  clearPoiList();
  Anim.reset();
  $("result-card").hidden = true;
  $("sim-card").hidden = true;
  $("poi-card").hidden = true;
  state.lastRouteCoords = null;
  state.lastRoutePath = null;
  if (which === "src") {
      applyStart(snap.lat, snap.lon);

      if (state.dst) {
        state.nextPick = "src";
        $("pick-hint").innerHTML = "Both points set. Click <b>Find path</b>, or click the map to restart.";
      } else {
        state.nextPick = "dst";
        $("pick-hint").innerHTML = "Start set from landmark. Click the map or choose a landmark to set the <b>end</b> point.";
      }
    } else {
      applyEnd(snap.lat, snap.lon);

      if (state.src) {
        state.nextPick = "src";
        $("pick-hint").innerHTML = "Both points set. Click <b>Find path</b>, or click the map to restart.";
      } else {
        state.nextPick = "src";
        $("pick-hint").innerHTML = "End set from landmark. Click the map or choose a landmark to set the <b>start</b> point.";
      }
    }

    setStatus("");
}

async function handlePick(latlng) { // used when click on map to pick start,end
  const { lat, lng } = latlng;
  if (state.src && state.dst) resetPoints(); 

  let snap;
  try {
    snap = await Api.nearest(lat, lng, currentSnapMode());
  } catch (err) {
    setStatus(err.message, "err");
    return;
  }

  if (!snap.ok) {
    setStatus(
      `Nearest road is ${Math.round(snap.distance_m)} m away — outside the local network. Pick another point.`,
      "err"
    );
    return;
  }
  if (state.nextPick === "src") {
    applyStart(snap.lat, snap.lon);
    state.nextPick = "dst";
    $("pick-hint").innerHTML = "Start set (snapped to nearest node). Click again to set the <b>end</b> point.";
  } else {
    applyEnd(snap.lat, snap.lon);
    state.nextPick = "src";
    $("pick-hint").innerHTML = "Both points set. Click <b>Find path</b>, or click the map to restart.";
  }
  setStatus("");
}

function resetPoints() {
  state.src = state.dst = null;
  state.nextPick = "src";
  ["src-lat", "src-lon", "dst-lat", "dst-lon"].forEach((id) => ($(id).value = ""));
  const ps = $("place-start"), pe = $("place-end");   
  if (ps) ps.value = "";
  if (pe) pe.value = "";

  MapView.clearPoints();
  MapView.clearRoute();
  Anim.reset();
  $("result-card").hidden = true;
  $("sim-card").hidden = true;
  $("poi-card").hidden = true;
  MapView.clearPois();
  clearPoiList();
  state.lastRouteCoords = null;
  state.lastRoutePath = null;
  $("pick-hint").innerHTML = "Click the map: 1st click sets <b>start</b>, 2nd sets <b>end</b>.";
  refreshRouteButton();
  setStatus("");
}

function readManualPoints() { 
  const sl = parseFloat($("src-lat").value), so = parseFloat($("src-lon").value);
  const dl = parseFloat($("dst-lat").value), dno = parseFloat($("dst-lon").value);
  if (!isNaN(sl) && !isNaN(so)) applyStart(sl, so);
  if (!isNaN(dl) && !isNaN(dno)) applyEnd(dl, dno);
}

function currentWeight() {
  return document.querySelector('input[name="weight"]:checked').value;
}
function currentSnapMode() {
  return $("snap-mode") ? $("snap-mode").value : "nearest_node";
}

async function runRoute() {
  readManualPoints();
  if (!state.src || !state.dst) { setStatus("Select both points.", "err"); return; }

  setStatus("Running Dijkstra…");
  $("btn-route").disabled = true;
  try {
    const res = await Api.route(state.src, state.dst, currentWeight(), currentSnapMode(), true, 4000); // # step traces 

    if (!res.found) {
      MapView.clearRoute();
      MapView.clearPois();
      $("result-card").hidden = true;
      $("poi-card").hidden = true;
      state.lastRouteCoords = null;
      state.lastRoutePath = null;
      setStatus(res.message, "err"); // Still load steps so the explored frontier remains inspectable.
      Anim.load(res);
      renderStepLog();
      $("sim-card").hidden = res.steps.length === 0;
      $("step-total").textContent = res.steps.length;
      return;
    }

    MapView.drawRoute(res.path_coords);
    state.lastRouteCoords = res.path_coords;
    state.lastRoutePath = res.path;
    MapView.clearPois();
    clearPoiList();
    $("poi-card").hidden = false;
    fillResult(res, currentWeight());
    Anim.load(res);
    renderStepLog();
    $("sim-card").hidden = false;
    $("step-total").textContent = res.steps.length;
    $("step-idx").textContent = 0;
    setStatus(res.message, "ok");
  } catch (err) {
    setStatus(err.message, "err");
  } finally {
    refreshRouteButton();
  }
}
async function runNearestFacility() {
  readManualPoints();
  if (!state.src) { setStatus("Pick a start point first.", "err"); return; }
  const sel = $("facility-type");
  const type = sel ? sel.value : "fuel";

  setStatus("Searching nearest…");
  $("btn-nearest").disabled = true;
  try {
    const res = await Api.nearestFacility(state.src, type, currentWeight(), currentSnapMode());

    if (!res.found) {
      MapView.clearRoute();
      MapView.clearPois();
      $("result-card").hidden = true;
      setStatus(res.message, "err");
      Anim.load(res);
      renderStepLog();
      $("poi-card").hidden = true;
      $("result-card").hidden = true;
      state.lastRouteCoords = null;
      state.lastRoutePath = null;
      $("sim-card").hidden = res.steps.length === 0;
      $("step-total").textContent = res.steps.length;
      return;
    }
    const endCoord =
      res.target_snapped_coord && res.target_snapped_coord.length
        ? res.target_snapped_coord
        : [res.poi_lat, res.poi_lon];    
    applyEnd(endCoord[0], endCoord[1]);
    MapView.drawRoute(res.path_coords);
    MapView.clearPois();
    clearPoiList();
    $("poi-card").hidden = false;
    state.lastRoutePath = res.path;          // so POIs-along-route can reuse it
    state.lastRouteCoords = res.path_coords;
    fillFacilityResult(res);
    Anim.load(res);
    renderStepLog();
    $("sim-card").hidden = false;
    $("step-total").textContent = res.steps.length;
    $("step-idx").textContent = 0;
    setStatus(res.message, "ok");
  } catch (err) {
    setStatus(err.message, "err");
  } finally {
    $("btn-nearest").disabled = false;
    refreshRouteButton();
  }
}

function fillFacilityResult(res) {
  const w = currentWeight();
  const label = POI_TYPE_LABELS[res.poi_type] || res.poi_type;
  const srcSnapCoord = res.source_snapped_coord && res.source_snapped_coord.length ? res.source_snapped_coord : state.src;
  const dstSnapCoord = res.target_snapped_coord && res.target_snapped_coord.length ? res.target_snapped_coord : [res.poi_lat, res.poi_lon];
  const srcSnapDist = res.source_snap_distance || 0;
  const dstSnapDist = res.target_snap_distance || 0;
  $("r-criterion").textContent = `${w === "travel_time" ? "Fastest" : "Shortest"} to nearest ${label}`;
  $("r-src").textContent = `${fmtCoord(state.src)} -> ${fmtCoord(srcSnapCoord)} (${Math.round(srcSnapDist)} m)`;
  $("r-dst").textContent = `${res.poi_name} ${fmtCoord([res.poi_lat, res.poi_lon])}-> ${fmtCoord(dstSnapCoord)} (${Math.round(dstSnapDist)} m)`;
  $("r-len").textContent = fmtLen(res.total_length);
  $("r-time").textContent = fmtTime(res.total_time);
  $("r-nodes").textContent = res.num_nodes;
  $("r-visited").textContent = res.visited_count;
  $("r-len").classList.toggle("highlight", w !== "travel_time");
  $("r-time").classList.toggle("highlight", w === "travel_time");
  $("result-card").hidden = false;
}
function fmtLen(m) { return m >= 1000 ? (m / 1000).toFixed(2) + " km" : Math.round(m) + " m"; }
function fmtTime(s) {
  const m = Math.floor(s / 60), sec = Math.round(s % 60);
  return m > 0 ? `${m} min ${sec} s` : `${sec} s`;
}
function fmtCoord(coord) {
  if (!Array.isArray(coord) || coord.length < 2) return "—";

  const lat = Number(coord[0]);
  const lon = Number(coord[1]);

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return "—";

  return `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
}

function fillResult(res, weight) {
  $("r-criterion").textContent = weight === "travel_time" ? "Fastest (time)" : "Shortest (length)";
  $("r-src").textContent =
    `${fmtCoord(state.src)} → ${fmtCoord(res.source_snapped_coord)} (${Math.round(res.source_snap_distance)} m)`;
  $("r-dst").textContent =
    `${fmtCoord(state.dst)} → ${fmtCoord(res.target_snapped_coord)} (${Math.round(res.target_snap_distance)} m)`;
  $("r-len").textContent = fmtLen(res.total_length);
  $("r-time").textContent = fmtTime(res.total_time);
  $("r-nodes").textContent = res.num_nodes;
  $("r-visited").textContent = res.visited_count;
  $("r-len").classList.toggle("highlight", weight !== "travel_time");
  $("r-time").classList.toggle("highlight", weight === "travel_time");
  $("result-card").hidden = false;
}


const PSEUDO_PHASES = { pop: [4], settle: [5, 6], relax: [7, 8, 9, 10], stop: [11] };
let phaseTimers = [];
let nodeLabels = {}; 
function buildNodeLabels() {
  nodeLabels = {};
  let n = 0;
  const give = (id) => {
    if (id == null || id === Anim.sourceNode || id === Anim.targetNode) return;
    const key = String(id);
    if (nodeLabels[key] === undefined) nodeLabels[key] = "N" + (++n);
  };
  for (const s of Anim.steps) give(s.current);          // settled order
  for (const s of Anim.steps) {                         // remaining: neighbours/queue
    (s.updated || []).forEach(give);
    (s.relaxed_edges || []).forEach(([u, v]) => { give(u); give(v); });
    (s.frontier_preview || []).forEach((f) => give(f.node));
  }
}

function nodeLabel(id) {
  if (id === Anim.sourceNode) return "Source";
  if (id === Anim.targetNode) return "Target";
  return nodeLabels[String(id)] || id;
}

function clearPhaseTimers() {
  phaseTimers.forEach(clearTimeout);
  phaseTimers = [];
}

function highlightLines(lines) {
  document.querySelectorAll("#pseudo .pl").forEach((el) => {
    el.classList.toggle("active", lines.includes(Number(el.dataset.line)));
  });
}

function renderRelaxTable(step) {
  const tbody = document.querySelector("#relax-table tbody");
  const details = (step && step.relax_details) || [];
  const rows = details.slice(0, 5);
  tbody.innerHTML = rows
    .map(
      (r) =>
        `<tr class="${r.improved ? "improved" : ""}"><td>${nodeLabel(r.to)}</td><td>${r.weight.toFixed(0)}</td>` +
        `<td>${r.candidate_dist.toFixed(0)}</td><td>${r.improved ? "✓ updated" : "— kept"}</td></tr>`
    )
    .join("");
  const extra = details.length - rows.length;
  if (extra > 0) tbody.innerHTML += `<tr><td colspan="4" class="muted">+ ${extra} more edges…</td></tr>`;
  if (details.length === 0) tbody.innerHTML = `<tr><td colspan="4" class="muted">No edges to relax.</td></tr>`;
}

let nodeDist = {}; // node id -> shortest distance from source (m), recorded at settle time
let targetTouchStep = -1; // step where the target first gets a finite tentative dist

function buildNodeDist() {
  nodeDist = {};
  for (const s of Anim.steps) {
    const k = String(s.current);
    if (nodeDist[k] === undefined) nodeDist[k] = s.dist_current; // dist at settle = final shortest
  }
}

function nodeTooltip(id) {
  const label = (typeof nodeLabel === "function") ? nodeLabel(id) : id;
  const d = nodeDist[String(id)];
  return `<b>${label}</b><br>dist from source: ${d === undefined ? "?" : fmtLen(d)}` +
         `<br><span style="opacity:.55">OSM ${id}</span>`;
}

function renderFrontierTable(step) {
  const tbody = document.querySelector("#frontier-table tbody");
  const rows = (step && step.frontier_preview) || [];
  tbody.innerHTML = rows.map((f) => `<tr><td>${nodeLabel(f.node)}</td><td>${f.dist.toFixed(0)}</td></tr>`).join("");
  if (rows.length === 0) tbody.innerHTML = `<tr><td colspan="2" class="muted">Queue empty.</td></tr>`;
}

function renderStepLog() {
  buildNodeLabels();
  buildNodeDist();
  buildNarrationMarks();
  const tbody = document.querySelector("#step-log tbody");
  tbody.innerHTML = Anim.steps
    .map((s, i) =>
      `<tr data-i="${i}" title="OSM id: ${s.current}"><td>${i + 1}</td><td>${nodeLabel(s.current)}</td>` +
      `<td>${fmtLen(s.dist_current)}</td><td>${(s.relax_details || []).length}</td>` +
      `<td class="${s.updated.length ? "up" : ""}">${s.updated.length}</td></tr>`
    )
    .join("");
  $("log-hint").hidden = Anim.steps.length === 0;
}

function setActiveLogRow(pointer) {
  const rows = document.querySelectorAll("#step-log tbody tr");
  rows.forEach((r) => r.classList.remove("active"));
  if (pointer < 0 || pointer >= rows.length) return;
  const row = rows[pointer];
  row.classList.add("active");
  const wrap = document.querySelector(".step-log-wrap");  // Scroll only within the log container so the control buttons stay put.
  if (!wrap) return;
  const wrapRect = wrap.getBoundingClientRect();
  const rowRect = row.getBoundingClientRect();
  const head = wrap.querySelector("thead");
  const headH = head ? head.getBoundingClientRect().height : 0; // account for sticky header

  if (rowRect.top < wrapRect.top + headH) {
    wrap.scrollTop -= (wrapRect.top + headH - rowRect.top);
  } else if (rowRect.bottom > wrapRect.bottom) {
    wrap.scrollTop += (rowRect.bottom - wrapRect.bottom);
  }
}
function buildNarrationMarks() {
  targetTouchStep = -1;
  for (let i = 0; i < Anim.steps.length; i++) {
    if ((Anim.steps[i].updated || []).includes(Anim.targetNode)) { targetTouchStep = i; break; }
  }
}
function describeStep(step) {
  const i = Anim.pointer;                       // index of the step being shown
  const details = step.relax_details || [];
  const improved = details.filter((r) => r.improved);
  const label = nodeLabel(step.current);
  const dCur = fmtLen(step.dist_current);
  const isTarget = step.current === Anim.targetNode;
  const parts = [];

  if (i === 0) {
    parts.push(
      `<span class="callout start">▶ Start.</span> Push the <b>source</b> with dist <b>0</b> and ` +
      `settle it at once — it is the closest vertex to itself. The search now grows outward.`
    );
  } else {
    if (isTarget) parts.push(`<span class="callout stop">■ Target reached.</span>`);
    parts.push(`Pop <b>${label}</b> (dist <b>${dCur}</b>) — the smallest tentative distance in the queue.`);
    parts.push(
      `<b>Settle</b> it: ${dCur} is final. Every other route to ${label} would pass through a vertex ` +
      `whose dist is already ≥ ${dCur}, and with all edge weights ≥ 0 none can come out shorter.`
    );
    if (isTarget) parts.push(`Dijkstra stops here — the shortest path to the target is locked in.`);
  }

  if (details.length === 0) {
    parts.push(`No outgoing edges — nothing to relax.`);
  } else if (improved.length === 0) {
    parts.push(`Scan ${details.length} edge${details.length > 1 ? "s" : ""}; none beats a neighbour\u2019s current dist, so the queue and the tree are unchanged.`);
  } else {
    const named = improved.slice(0, 2).map((r) => `${nodeLabel(r.to)} ${fmtLen(r.candidate_dist)}`);
    const more = improved.length > named.length ? ", …" : "";
    parts.push(
      `Scan ${details.length} edge${details.length > 1 ? "s" : ""}; <b>${improved.length}</b> give${improved.length === 1 ? "s" : ""} ` +
      `a shorter path \u2192 <b>relax</b> and attach to the shortest-path tree (${named.join(", ")}${more}).`
    );
  }
  if (i === targetTouchStep && !isTarget) {
    parts.push(
      `<span class="callout touch">◆ The target just entered the queue</span> with a <i>tentative</i> ` +
      `distance — not final yet; a cheaper route may still appear before it is settled.`
    );
  }

  return parts.join(" ");
}

function renderPseudoWalkthrough(step) {
  clearPhaseTimers();
  if (!step) {
    highlightLines([]);
    $("narration").textContent = "";
    renderRelaxTable(null);
    renderFrontierTable(null);
    return;
  }
  $("narration").innerHTML = describeStep(step);
  renderRelaxTable(step);
  renderFrontierTable(step);
  highlightLines(PSEUDO_PHASES.pop);
  phaseTimers.push(setTimeout(() => highlightLines([...PSEUDO_PHASES.pop, ...PSEUDO_PHASES.settle]), 180));
  phaseTimers.push(setTimeout(() => highlightLines([...PSEUDO_PHASES.settle, ...PSEUDO_PHASES.relax]), 420));
  if (step.current === Anim.targetNode) {
    phaseTimers.push(setTimeout(() => highlightLines([...PSEUDO_PHASES.relax, ...PSEUDO_PHASES.stop]), 700));
  }
}

function onAnimUpdate(pointer, total, step, stoppedOnly) {
  $("step-idx").textContent = Math.max(0, pointer + 1);
  $("step-total").textContent = total;
  $("btn-sim-play").textContent = Anim.isPlaying() ? "⏸ Pause" : "▶ Play";
  setActiveLogRow(pointer);
  if (stoppedOnly) return; // not update the pseudo walkthrough if the animation is paused
  renderPseudoWalkthrough(pointer < 0 ? null : step);
}


function fillPlaceSelect(sel) {
  sel.length = 1; // keep placeholder option, drop the rest
  LANDMARKS.forEach((p, i) => {
    if (p.type && !LANDMARK_TYPES.has(p.type)) return; // keep utilities out of from/to
    const opt = document.createElement("option");
    opt.value = i; opt.textContent = p.name;
    sel.appendChild(opt);
  });
}

function fillFacilityTypes() {
  const sel = $("facility-type");
  if (!sel) return;
  const types = [...new Set(LANDMARKS.map((p) => p.type).filter(Boolean))].sort();
  sel.length = 0;
  types.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t; opt.textContent = POI_TYPE_LABELS[t] || t;
    sel.appendChild(opt);
  });
}

async function initLandmarks() {
  const placeStart = $("place-start");
  const placeEnd = $("place-end");
  if (!placeStart || !placeEnd) return; // dropdowns not present in index.html

  try {
    const list = (typeof Api.places === "function") ? await Api.places() : [];
    LANDMARKS = (Array.isArray(list) && list.length) ? list : LANDMARKS_FALLBACK;
  } catch {
    LANDMARKS = LANDMARKS_FALLBACK;
  }

  fillPlaceSelect(placeStart);
  fillPlaceSelect(placeEnd);
  fillPoiTypes();
  fillFacilityTypes();

  placeStart.addEventListener("change", (e) => {
    if (e.target.value === "") return;
    const p = LANDMARKS[Number(e.target.value)];
    setLandmarkEndpoint("src", p.lat, p.lon);
  });
  placeEnd.addEventListener("change", (e) => {
    if (e.target.value === "") return;
    const p = LANDMARKS[Number(e.target.value)];
    setLandmarkEndpoint("dst", p.lat, p.lon);
  });
}

function fillPoiTypes() {
  const sel = $("poi-type");
  if (!sel) return;
  const types = [...new Set(LANDMARKS.map((p) => p.type).filter(Boolean))].sort();
  sel.length = 1; // keep the '— all —' option
  types.forEach((t) => {
    const opt = document.createElement("option");
    opt.value = t; opt.textContent = POI_TYPE_LABELS[t] || t;
    sel.appendChild(opt);
  });
}

function clearPoiList() {
  const el = $("poi-list");
  if (el) el.innerHTML = "";
  lastPois = []; 1
}

function renderPoiList(pois) {
  const el = $("poi-list");
  if (!el) return;
  if (!pois.length) {
    el.innerHTML = `<li class="empty">No amenities of this type within range of the route.</li>`;
    return;
  }
  el.innerHTML = pois
    .map((p, i) => `<li data-i="${i}"><span>${p.name}</span>` +
                   `<span class="off">\u21B3 ${Math.round(p.detour_m)} m</span></li>`)
    .join("");
}

async function renderPoisAlongRoute() {
  if (!state.lastRoutePath || !state.lastRoutePath.length) return;
  const type = $("poi-type").value || null;
  const maxDetour = Number($("poi-radius").value) || 200;
  $("poi-list").innerHTML = `<li class="empty">Searching…</li>`;
  try {
    const res = await Api.poisAlongRoute(state.lastRoutePath, type, maxDetour);
    lastPois = res.pois || [];
    MapView.drawPois(lastPois);
    renderPoiList(lastPois);
  } catch (err) {
    MapView.clearPois();
    $("poi-list").innerHTML = `<li class="empty">${err.message}</li>`;
  }
}

function initControls() {
  MapView.onPick = handlePick;
  Anim.onUpdate = onAnimUpdate;

  $("btn-route").addEventListener("click", runRoute);
  { const b = $("btn-nearest"); if (b) b.addEventListener("click", runNearestFacility); }
  $("btn-reset-points").addEventListener("click", resetPoints);

  document.querySelectorAll('input[name="weight"]').forEach((r) =>
    r.addEventListener("change", () => {
      if (!$("result-card").hidden) {
        setStatus('Weight changed — click "Find path" to recompute.', "");
      }
    })
  );

  $("sample").addEventListener("change", (e) => {
    const i = e.target.value;
    if (i === "") return;
    const p = SAMPLE_POINTS[Number(i)];
    resetPoints();
    applyStart(p.src[0], p.src[1]);
    applyEnd(p.dst[0], p.dst[1]);
    state.nextPick = "src";
  });

  $("btn-sim-next").addEventListener("click", () => Anim.next());
  $("btn-sim-prev").addEventListener("click", () => Anim.prev());
  $("btn-sim-reset").addEventListener("click", () => Anim.reset());
  $("btn-sim-play").addEventListener("click", () => {
    if (Anim.isPlaying()) Anim.stop(); else Anim.play();
    $("btn-sim-play").textContent = Anim.isPlaying() ? "⏸ Pause" : "▶ Play";
  });
  document.querySelector("#step-log tbody").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-i]");
    if (tr) Anim.goto(Number(tr.dataset.i));
  });
  $("speed").addEventListener("input", (e) => Anim.setSpeed(Number(e.target.value)));

  const sptToggle = $("show-spt");
  if (sptToggle) {
    sptToggle.addEventListener("change", (e) => {
      MapView.setSptVisible(e.target.checked); 
      Anim.rerender(); // refresh dist labels on the current step
    });
  }

  $("btn-poi").addEventListener("click", renderPoisAlongRoute);
  $("poi-type").addEventListener("change", renderPoisAlongRoute);
  $("poi-radius").addEventListener("change", renderPoisAlongRoute);
  $("poi-list").addEventListener("click", (e) => {
    const li = e.target.closest("li[data-i]");
    if (!li) return;
    const p = lastPois[Number(li.dataset.i)];
    if (p) MapView.panTo(p.lat, p.lon);
  });

  SAMPLE_POINTS.forEach((p, i) => {
    const opt = document.createElement("option");
    opt.value = i; opt.textContent = p.name;
    $("sample").appendChild(opt);
  });

  initLandmarks();
}

async function main() {
  initControls();
  try {
    const meta = await Api.meta();
    MapView.init(meta);
    Anim.setSpeed(Number($("speed").value));
    $("meta-line").textContent =
      `${meta.num_nodes} nodes · ${meta.num_edges} edges · real road network`;
  } catch (err) {
    $("meta-line").textContent = "Graph load error: " + err.message;
  }
}

main();