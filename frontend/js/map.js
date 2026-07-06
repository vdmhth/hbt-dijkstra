const MapView = {
  map: null,
  startMarker: null,
  endMarker: null,
  routeLayer: null,
  vizRenderer: null,    // canvas renderer -> draw thousands of markers without lag
  sptRenderer: null,    // separate canvas (lower pane) so tree edges sit under the dots
  settledLayer: null,   // settled vertices (accumulated)
  transientLayer: null, // current / updated vertices and relaxing edges (cleared each step)
  sptLayer: null,       // shortest-path tree, grows as relaxations succeed (accumulated)
  poiLayer: null,       // POIs near the found route
  settledMarkers: null, // Map<nodeId, marker> for add/remove on step forward/back
  sptEdges: null,       // Map<childId, polyline> -> one tree edge per relaxed vertex
  showSpt: true,        // toggle: draw the SPT and dist labels
  onPick: null,         // callback(latlng) on map click

  init(meta) {
    this.map = L.map("map", { maxBoundsViscosity: 1.0 });
    const tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      crossOrigin: true,
      updateWhenIdle: true,   // wait until finish panning
      keepBuffer: 4,          // keep tiles around viewport
      attribution: "© OpenStreetMap",
    }).addTo(this.map);

    tiles.on("tileerror", (e) => { // handle wwhen tiles fail
      const img = e.tile;
      const n = (img._retry || 0) + 1;
      if (n > 2) return;
      img._retry = n;
      const src = img.src;
      img.src = "";
      setTimeout(() => { img.src = src; }, 400 * n);  
    });
    const b = meta.bounds; // [min_lat, min_lon, max_lat, max_lon]
    const area = L.latLngBounds([b[0], b[1]], [b[2], b[3]]);

    const world = [[-90, -360], [90, -360], [90, 360], [-90, 360]]; // dim the outside
    const hole = [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]];
    L.polygon([world, hole], {
      stroke: false, fillColor: "#0b0e14", fillOpacity: 0.96, interactive: false,
    }).addTo(this.map);
    const lockToArea = () => {
      this.map.invalidateSize();
      const coverZoom = this.map.getBoundsZoom(area, true);
      this.map.setView(area.getCenter(), coverZoom, { animate: false });
      this.map.setMinZoom(coverZoom);
      this.map.setMaxBounds(area.pad(0.02)); // slight slack so the view does not snap back
    };
    this.map.whenReady(lockToArea);
    setTimeout(lockToArea, 400); // re-run after layout settles, just in case
    window.addEventListener("resize", lockToArea);

    //SPT edges drawn under vertices
    this.map.createPane("sptPane");
    this.map.getPane("sptPane").style.zIndex = 350; // overlayPane (markers) is 400
    this.sptRenderer = L.canvas({ pane: "sptPane", padding: 0.5 });

    this.vizRenderer = L.canvas({ padding: 0.5, tolerance: 12 }); 
    this.sptLayer = L.layerGroup().addTo(this.map);
    this.settledLayer = L.layerGroup().addTo(this.map);
    this.transientLayer = L.layerGroup().addTo(this.map);
    this.poiLayer = L.layerGroup().addTo(this.map);
    this.settledMarkers = new Map();
    this.sptEdges = new Map();
    // Shared tooltip: on hover, show the nearest settled node to the cursor.
    this.hoverTip = L.tooltip({ direction: "top", offset: [0, -4], sticky: true });
    this.map.on("mousemove", (e) => this._hoverSettled(e));
    this.map.on("mouseout", () => this.map.removeLayer(this.hoverTip));

    this.map.on("click", (e) => this.onPick && this.onPick(e.latlng));
  },
  setStart(lat, lon) {
    if (this.startMarker) this.map.removeLayer(this.startMarker);
    this.startMarker = L.marker([lat, lon], { title: "Start" })
      .addTo(this.map).bindPopup("Start");
    this.startMarker._icon && (this.startMarker._icon.style.filter = "hue-rotate(95deg)"); // only run if the latter exists
  },
  setEnd(lat, lon) {
    if (this.endMarker) this.map.removeLayer(this.endMarker);
    this.endMarker = L.marker([lat, lon], { title: "End" })
      .addTo(this.map).bindPopup("End");
    this.endMarker._icon && (this.endMarker._icon.style.filter = "hue-rotate(0deg)"); // only run if the latter exists
  },
  clearPoints() {
    if (this.startMarker) { this.map.removeLayer(this.startMarker); this.startMarker = null; }
    if (this.endMarker) { this.map.removeLayer(this.endMarker); this.endMarker = null; }
  },

  //result route
  drawRoute(coords) {
    this.clearRoute();
    this.routeLayer = L.polyline(coords, {
      color: getCss("--accent"), weight: 6, opacity: 0.7,
    }).addTo(this.map);
    this.map.fitBounds(this.routeLayer.getBounds(), { padding: [40, 40] });
  },
  clearRoute() {
    if (this.routeLayer) { this.map.removeLayer(this.routeLayer); this.routeLayer = null; }
  },

  // algorithm simulation
  clearViz() {
    this.settledLayer.clearLayers();
    this.transientLayer.clearLayers();
    this.sptLayer.clearLayers();
    this.settledMarkers.clear();
    this.sptEdges.clear();
  },
  addSettled(coords) {
      for (const [id, lat, lon] of coords) {
        if (this.settledMarkers.has(id)) continue;
        const m = L.circleMarker([lat, lon], {
          renderer: this.vizRenderer, radius: 4, interactive: true,
          color: getCss("--settled"), fillColor: getCss("--settled"),
          fillOpacity: 0.85, weight: 0.1,
        }).addTo(this.settledLayer);
        this.settledMarkers.set(id, m);
      }
    },

  removeSettled(ids) {
    for (const id of ids) {
      const m = this.settledMarkers.get(id);
      if (m) { this.settledLayer.removeLayer(m); this.settledMarkers.delete(id); }
    }
  },
  setSptEdge(childId, parentLatLon, childLatLon) {
    const old = this.sptEdges.get(childId);
    if (old) this.sptLayer.removeLayer(old);  // remove the old edge if it exists
    const line = L.polyline([parentLatLon, childLatLon], {
      renderer: this.sptRenderer, color: getCss("--tree"),
      weight: 2.2, opacity: 0.85, interactive: false,
    }).addTo(this.sptLayer);
    this.sptEdges.set(childId, line);
  },
  removeSptEdge(childId) {
    const line = this.sptEdges.get(childId);
    if (line) { this.sptLayer.removeLayer(line); this.sptEdges.delete(childId); }
  },
  setSptVisible(on) {
    this.showSpt = on;
    if (on) {
      if (!this.map.hasLayer(this.sptLayer)) this.sptLayer.addTo(this.map);
    } else {
      this.map.removeLayer(this.sptLayer);
    }
  },

  clearPois() { if (this.poiLayer) this.poiLayer.clearLayers(); },
  drawPois(hits) {
    this.clearPois();
    for (const h of hits) {
      const line = (h.turn_in && h.turn_in.length ? h.turn_in.slice() : [[h.attach_lat, h.attach_lon]]); //copy array 
      line.push([h.lat, h.lon]);
      L.polyline(line, {
        color: getCss("--poi"), weight: 2, opacity: 0.85, dashArray: "4 4", interactive: false,
      }).addTo(this.poiLayer);
      L.circleMarker([h.lat, h.lon], {
        radius: 6, color: "#fff", weight: 1.5,
        fillColor: getCss("--poi"), fillOpacity: 1,
      })
        .bindTooltip(`<b>${h.name}</b><br>${Math.round(h.detour_m)} m detour off the route`,
                     { direction: "top", offset: [0, -6] })
        .addTo(this.poiLayer);
    }
  },
  panTo(lat, lon) { if (this.map) this.map.panTo([lat, lon]); }, // keep zoom, change center
  _hoverSettled(e) {
    if (!this.settledMarkers || this.settledMarkers.size === 0) {
      this.map.removeLayer(this.hoverTip);
      return;
    }
    const p = e.containerPoint;
    let bestId = null, bestLL = null, bestD = 12; // hit threshold: 12px
    for (const [id, m] of this.settledMarkers) {
      const mp = this.map.latLngToContainerPoint(m.getLatLng());
      const d = mp.distanceTo(p);
      if (d < bestD) { bestD = d; bestId = id; bestLL = m.getLatLng(); }
    }
    if (bestId !== null) {
      this.hoverTip
        .setLatLng(bestLL)
        .setContent(typeof nodeTooltip === "function" ? nodeTooltip(bestId) : String(bestId));
      if (!this.map.hasLayer(this.hoverTip)) this.hoverTip.addTo(this.map);
    } else {
      this.map.removeLayer(this.hoverTip);
    }
  },
  _distLabel(latlon, dist, cls) {
    if (dist === undefined || dist === null) return;
    const txt = (typeof fmtLen === "function") ? fmtLen(dist) : Math.round(dist) + " m";
    L.tooltip({
      permanent: true, direction: "top", offset: [0, -7],
      className: "dist-label " + cls, opacity: 1,
    }).setLatLng(latlon).setContent(txt).addTo(this.transientLayer);
  },
  drawTransient(current, updatedItems, relaxSegments) {
    this.transientLayer.clearLayers();
    for (const seg of relaxSegments) {
      L.polyline(seg, { renderer: this.vizRenderer, color: getCss("--relax"), weight: 1.5, opacity: 0.7 })
        .addTo(this.transientLayer);
    }
    for (const it of updatedItems) {
      L.circleMarker(it.latlon, {
        renderer: this.vizRenderer, radius: 4,
        color: getCss("--updated"), fillColor: getCss("--updated"), fillOpacity: 0.95, weight: 0,
      }).addTo(this.transientLayer);
      if (this.showSpt) this._distLabel(it.latlon, it.dist, "updated");
    }
    if (current && current.latlon) {
      L.circleMarker(current.latlon, {
        renderer: this.vizRenderer, radius: 6,
        color: "#fff", fillColor: getCss("--current"), fillOpacity: 1, weight: 1.5,
      }).addTo(this.transientLayer);
      if (this.showSpt) this._distLabel(current.latlon, current.dist, "current");
    }
  },
};

function getCss(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}