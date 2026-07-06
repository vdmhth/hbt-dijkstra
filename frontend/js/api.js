const Api = {
  async meta() {
    const res = await fetch("/api/meta");
    if (!res.ok) throw new Error("Cannot load map metadata.");
    return res.json();
  },

  async nearest(lat, lon, snapMode = "nearest_node") {
    const url = `/api/nearest?lat=${lat}&lon=${lon}&snap_mode=${snapMode}`;
    const res = await fetch(url);

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(data.detail || "Cannot check this location.");
    }

    return data;
  },
  async places() {
    const res = await fetch("/api/places");
    return res.ok ? res.json() : [];
  },

  async route(
    source,
    target,
    weight,
    snapMode = "nearest_node",
    recordSteps = true,
    maxSteps = 4000
  ) {
    const res = await fetch("/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: { lat: source[0], lon: source[1] },
        target: { lat: target[0], lon: target[1] },
        weight,
        snap_mode: snapMode,
        record_steps: recordSteps,
        max_steps: maxSteps,
      }),
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(data.detail || "Error occurred while finding the route.");
    }

    return data;
  },

  async poisAlongRoute(path, type = null, maxDetourM = 200) {
    const res = await fetch("/pois_along_route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, type, max_detour_m: maxDetourM }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Could not load POIs along the route.");
    return data;
  },

  async nearestFacility(source, type, weight = "length",snapMode= "nearest_node") {
    const res = await fetch("/nearest_facility", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source: { lat: source[0], lon: source[1] },
        type, weight,snap_mode: snapMode, record_steps: true, max_steps: 4000,
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Nearest-facility search failed.");
    return data;
  },
};