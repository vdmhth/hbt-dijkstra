const Anim = {
  steps: [],
  coords: {},      
  sourceNode: null,
  targetNode: null,
  pointer: -1,    
  timer: null,
  speed: 40,      
  onUpdate: null, 

  load(response) {
    this.stop();
    this.steps = response.steps || [];
    this.coords = response.node_coords || {};
    this.sourceNode = response.source_node;
    this.targetNode = response.target_node;
    this.pointer = -1;
    this._buildSptDeltas();
    MapView.clearViz();
    this._emit(null);
  },

  latlon(id) {
    return this.coords[String(id)];
  },
  _buildSptDeltas() {
    const parent = {};
    for (const s of this.steps) {
      s._sptPrev = {};
      for (const v of (s.updated || [])) {
        s._sptPrev[v] = (v in parent) ? parent[v] : null;
        parent[v] = s.current;
      }
    }
  },
  _applySpt(step) {
    const pll = this.latlon(step.current);
    if (!pll) return;
    for (const v of (step.updated || [])) {
      const cll = this.latlon(v);
      if (cll) MapView.setSptEdge(v, pll, cll);
    }
  },
  _undoSpt(step) {
    for (const v of (step.updated || [])) {
      const prior = step._sptPrev ? step._sptPrev[v] : null;
      const cll = this.latlon(v);
      const pll = prior == null ? null : this.latlon(prior);
      if (pll && cll) MapView.setSptEdge(v, pll, cll);
      else MapView.removeSptEdge(v);
    }
  },

  _renderStep(step) {
    const cur = this.latlon(step.current); // popped node
    const current = cur ? { latlon: cur, dist: step.dist_current } : null;
    const newDist = {};
    for (const r of (step.relax_details || [])) {
      if (r.improved) newDist[r.to] = r.candidate_dist;
    }
    const updated = (step.updated || [])
      .map((id) => {
        const ll = this.latlon(id);
        return ll ? { latlon: ll, dist: newDist[id] } : null;
      })
      .filter(Boolean);
    const relax = (step.relaxed_edges || [])
      .map(([u, v]) => {
        const a = this.latlon(u), b = this.latlon(v);
        return a && b ? [a, b] : null;
      })
      .filter(Boolean);
    MapView.drawTransient(current, updated, relax);
  },

  rerender() {
    if (this.pointer >= 0 && this.pointer < this.steps.length) {
      this._renderStep(this.steps[this.pointer]);
    }
  },

  next() {
    if (this.pointer >= this.steps.length - 1) { this.stop(); return false; }
    this.pointer++;
    const step = this.steps[this.pointer];
    const settled = step.settled
      .map((id) => { const c = this.latlon(id); return c ? [id, c[0], c[1]] : null; })
      .filter(Boolean);
    MapView.addSettled(settled);
    this._applySpt(step);
    this._renderStep(step);
    this._emit(step);
    return true;
  },

  prev() {
    if (this.pointer < 0) return false;
    const step = this.steps[this.pointer];
    this._undoSpt(step);                  
    MapView.removeSettled(step.settled);   
    this.pointer--;
    if (this.pointer >= 0) {
      this._renderStep(this.steps[this.pointer]);
      this._emit(this.steps[this.pointer]);
    } else {
      MapView.transientLayer.clearLayers();
      this._emit(null);
    }
    return true;
  },
  goto(index) {
    this.stop(); // stop if the animation is running
    index = Math.max(-1, Math.min(index, this.steps.length - 1));
    MapView.clearViz();
    this.pointer = -1;  // reset pointer and rerun from step 0 to index
    for (let i = 0; i <= index; i++) {
      this.pointer = i;
      const step = this.steps[i];
      const settled = step.settled
        .map((id) => { const c = this.latlon(id); return c ? [id, c[0], c[1]] : null; })
        .filter(Boolean);
      MapView.addSettled(settled);
      this._applySpt(step);
    }
    if (index >= 0) {
      this._renderStep(this.steps[index]);
      this._emit(this.steps[index]);
    } else {
      MapView.transientLayer.clearLayers();
      this._emit(null);
    }
  },
  reset() {
    this.stop();
    this.pointer = -1;
    MapView.clearViz();
    this._emit(null);
  },

  play() {
    if (this.timer) return;
    if (this.pointer >= this.steps.length - 1) this.reset(); // if at the end, reset to start
    const tick = () => {
      const ok = this.next();
      if (!ok) { this.stop(); return; }
      this.timer = setTimeout(tick, 1000 / this.speed);
    };
    tick();
  },

  stop() {
    if (this.timer) { clearTimeout(this.timer); this.timer = null; }
    this._emit(this.pointer >= 0 ? this.steps[this.pointer] : null, true);
  },

  setSpeed(v) { this.speed = Math.max(1, v); },

  isPlaying() { return this.timer != null; },

  _emit(step, stoppedOnly = false) {
    if (this.onUpdate) this.onUpdate(this.pointer, this.steps.length, step, stoppedOnly);
  },
};