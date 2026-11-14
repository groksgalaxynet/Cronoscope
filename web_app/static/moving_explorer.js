(() => {
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? "unavailable").replace(/[&<>]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[char]));
  const num = (value, digits=4) => value == null ? "unavailable" : Number(value).toFixed(digits);
  const date = value => value ? new Date(value).toLocaleString() : "unavailable";
  let catalog = [];
  async function get(path) {
    const response = await fetch(path);
    let payload;
    try { payload = await response.json(); }
    catch { throw new Error(`request failed: HTTP ${response.status}; catalog response was not JSON`); }
    if (!response.ok || payload.status !== "SUCCESS") {
      const detail = payload.errors?.join(" ") || payload.status || "catalog unavailable";
      throw new Error(`request failed: HTTP ${response.status}; ${detail}`);
    }
    return payload;
  }
  function render(detail) {
    const [oldObservation, newObservation] = detail.observations;
    $("moving-target-header").innerHTML = `<b>${esc(detail.target.label)}</b><br><span>${esc(detail.target.type)} · ${detail.observations.length} observations</span><br><small>${date(oldObservation.epoch_utc)} → ${date(newObservation.epoch_utc)}</small>`;
    $("moving-timeline").innerHTML = detail.observations.map((observation, index) => `<button class="timeline-item ${observation.role}" data-role="${observation.role}"><b>${index + 1}. ${esc(observation.role.toUpperCase())}</b><br>${date(observation.epoch_utc)}<br>${esc(observation.observation_id)} · ${esc(observation.wavelength.band_label)}<br>${num(observation.wavelength.minimum_m * 1e6,3)}–${num(observation.wavelength.maximum_m * 1e6,3)} µm</button>`).join("");
    $("moving-motion").innerHTML = `<h2>Predicted motion</h2><b>Old → new</b><br>${date(oldObservation.epoch_utc)} → ${date(newObservation.epoch_utc)}<br>RA/Dec old: ${num(oldObservation.sky_position.ra_deg,6)}°, ${num(oldObservation.sky_position.dec_deg,6)}°<br>RA/Dec new: ${num(newObservation.sky_position.ra_deg,6)}°, ${num(newObservation.sky_position.dec_deg,6)}°<br><span class="motion-arrow">OLD → NEW</span><br>Elapsed ${num(detail.motion.elapsed_seconds,1)} s · displacement ${num(detail.motion.angular_displacement_deg,6)}° · rate ${num(detail.motion.apparent_angular_rate_deg_per_day,6)}°/day`;
    $("moving-spectral").innerHTML = `<h2>Observation / wavelength</h2>${detail.observations.map(o => `<b>${esc(o.role.toUpperCase())}</b> · ${esc(o.wavelength.band_label)}<br>${num(o.wavelength.minimum_m * 1e6,3)}–${num(o.wavelength.maximum_m * 1e6,3)} µm<br><small>${esc(o.observation_id)}</small><br>`).join("")}`;
    const v2 = detail.v2_evidence;
    $("moving-v2").innerHTML = v2.status === "AVAILABLE" ? `<h2>Experimental image evidence — not a detection</h2><b>Frozen V2 percentile: ${num(v2.percentile,6)}</b><br>Signed old measurement: ${num(v2.signed_old_measurement,6)}<br>Signed new measurement: ${num(v2.signed_new_measurement,6)}<br>Both-sign result: ${v2.both_sign_result ? "true" : "false"}<br>Control distribution: ${v2.control_count} frozen controls` : `<h2>Experimental image evidence — not a detection</h2><b>Frozen V2 record is invalid</b><br>${esc(v2.reason)}<br>No percentile is assigned.`;
    $("moving-provenance").innerHTML = `SPHEREx/IRSA: ${esc(detail.provenance.spherex)}<br>Coordinates: ${esc(detail.motion.coordinate_provenance)}<br>Evidence: ${esc(detail.provenance.evidence)}<br>Images are retrieved on demand from the observation IDs above; no detector is rerun.`;
    for (const observation of detail.observations) $("moving-" + observation.role + "-image").src = `/api/moving-objects/${encodeURIComponent(detail.target.id)}/image/${observation.role}`;
    document.querySelectorAll(".timeline-item").forEach(button => button.onclick = () => $("moving-" + button.dataset.role + "-image").scrollIntoView({behavior:"smooth", block:"center"}));
  }
  async function choose(id) { const response = await get(`/api/moving-objects/${encodeURIComponent(id)}`); if (response.status === "SUCCESS") render(response.data); }
  async function open() {
    $("moving-explorer").hidden = false;
    if (catalog.length) return;
    try {
      const response = await get("/api/moving-objects"); catalog = response.data.targets;
      if (!Array.isArray(catalog) || !catalog.length) throw new Error("catalog unavailable: no frozen targets returned");
      $("moving-target-select").innerHTML = catalog.map(item => `<option value="${esc(item.target.id)}">${esc(item.target.label)} · ${esc(item.band_labels.join(", "))}</option>`).join("");
      $("moving-target-select").onchange = event => choose(event.target.value);
      await choose(catalog[0].target.id);
    } catch (error) {
      $("moving-target-select").innerHTML = `<option>Catalog unavailable — ${esc(error.message)}</option>`;
      $("moving-target-header").textContent = `Catalog unavailable: ${error.message}`;
      $("moving-target-select").disabled = true;
    }
  }
  $("open-moving-explorer").onclick = open; $("close-moving-explorer").onclick = () => { $("moving-explorer").hidden = true; };
})();
