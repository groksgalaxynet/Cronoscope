(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const state = {targets: [], targetId: null, metadata: null, fitScale: 1, zoom: 1, panX: 0, panY: 0, drag: null, overlay: []};
  const esc = value => String(value ?? "—").replace(/[&<>]/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;"}[c]));
  const number = (value, digits = 5) => value == null ? "—" : Number(value).toFixed(digits);
  const api = path => fetch(path).then(async response => {
    const body = await response.json();
    if (!response.ok) throw new Error(body.errors?.join(" ") || body.status || "Request failed");
    return body;
  });

  function activeTarget() { return state.targets.find(target => target.target_id === state.targetId); }
  function image() { return $("science-image"); }
  function transform() { image().style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.fitScale * state.zoom})`; }
  function fitToCanvas(reset = false) {
    const element = image(), canvas = $("science-canvas");
    if (!element.naturalWidth || !element.naturalHeight || !canvas.clientWidth || !canvas.clientHeight) return;
    state.fitScale = Math.min(canvas.clientWidth / element.naturalWidth, canvas.clientHeight / element.naturalHeight);
    if (reset) { state.zoom = 1; state.panX = 0; state.panY = 0; }
    $("science-view-scale").textContent = `Fit ${number(state.fitScale, 1)}× · zoom ${number(state.zoom, 2)}×`;
    transform(); drawOverlay();
  }
  function resetView() { state.zoom = 1; state.panX = 0; state.panY = 0; fitToCanvas(true); }

  function renderMetadata(data) {
    const target = data.target, visual = data.visualization;
    $("science-target-status").textContent = `${target.target_name} · ${target.detector}`;
    $("science-product-summary").innerHTML = `<b>${esc(target.product_filename)}</b><br>` +
      `Release ${esc(target.release)} · MJD ${number(target.mjd, 6)}<br>` +
      `${number(target.wavelength_min_um, 4)}–${number(target.wavelength_max_um, 4)} µm · ${esc(visual.image_unit || "unit unavailable")}<br>` +
      `Finite/invalid pixels: ${visual.finite_pixel_count}/${visual.invalid_pixel_count}<br>` +
      `Scaling: ${esc(visual.intensity_scale?.method || "unavailable")} ${number(visual.intensity_scale?.lower_percentile, 0)}–${number(visual.intensity_scale?.upper_percentile, 0)} percentile.`;
    const wavelength = $("science-wavelength"), contextRange = visual.wavelength_context?.wavelength_range_um;
    const low = contextRange?.[0] ?? target.wavelength_min_um, high = contextRange?.[1] ?? target.wavelength_max_um;
    wavelength.min = String(low); wavelength.max = String(high);
    wavelength.value = String(visual.recommended_wavelength_um ?? (low + high) / 2); wavelength.disabled = false;
    $("science-wavelength-label").textContent = `${number(wavelength.value, 3)} µm`;
  }

  async function loadTarget(targetId) {
    state.targetId = targetId; state.metadata = null; state.overlay = [];
    $("science-overlay").hidden = true;
    $("science-panel-data").textContent = "No pixel selected. Source spectrum unavailable — local WCS-WAVE context only.";
    $("science-target-status").textContent = "Loading genuine local FITS product…";
    try {
      const response = await api(`/api/viewer/${encodeURIComponent(targetId)}/metadata`);
      state.metadata = response.data; renderMetadata(response.data); resetView();
      image().src = `/api/viewer/${encodeURIComponent(targetId)}/image`;
      image().alt = `${response.data.target.target_name} genuine SPHEREx Level-2 science image`;
      await updateOverlap();
      if ($("science-overlay-visible").checked) await updateOverlay();
    } catch (error) { $("science-target-status").textContent = `Viewer unavailable: ${error.message}`; }
  }

  function imagePoint(event) {
    const element = image(), rect = element.getBoundingClientRect();
    return {x: (event.clientX - rect.left) / rect.width * element.naturalWidth,
            y: (event.clientY - rect.top) / rect.height * element.naturalHeight};
  }

  function panel(data) {
    const readout = data.readout, wave = readout.wavelength_context;
    $("science-panel-data").innerHTML = `<div><b>${esc(data.target.target_name)} · ${esc(data.target.product_filename)}</b></div>` +
      `<div>Pixel: (${number(readout.x, 2)}, ${number(readout.y, 2)}) · RA ${number(readout.ra_deg, 7)}° · Dec ${number(readout.dec_deg, 7)}°</div>` +
      `<div>Science intensity: ${number(readout.science_value, 8)} ${esc(readout.image_unit)} · valid: ${readout.science_value_valid}</div>` +
      `<div>Variance: ${number(readout.variance, 8)} · Raw quality flag: ${esc(readout.quality_flags)} <small>(raw value; no bit semantics inferred)</small></div>` +
      `<div>Local WCS-WAVE: ${number(wave.wavelength_um, 6)} µm · bandwidth ${number(wave.bandwidth_um, 6)} µm · ${esc(wave.status)}</div>` +
      `<div>Observation MJD: ${number(data.target.mjd, 6)} · Release: ${esc(data.target.release)} · Detector: ${esc(data.target.detector)}</div>` +
      `<div class="science-warning">${esc(data.source_spectrum)}</div>` + (readout.warning ? `<div class="science-warning">${esc(readout.warning)}</div>` : "");
    $("science-panel").open = true;
  }

  function drawOverlay() {
    const layer = $("science-overlay"), element = image();
    layer.replaceChildren();
    if (!state.overlay.length || !element.naturalWidth) { layer.hidden = true; return; }
    const rect = element.getBoundingClientRect(), container = $("science-canvas").getBoundingClientRect();
    layer.style.left = `${rect.left - container.left}px`; layer.style.top = `${rect.top - container.top}px`;
    layer.style.width = `${rect.width}px`; layer.style.height = `${rect.height}px`; layer.hidden = false;
    state.overlay.forEach(pixel => { const dot = document.createElement("i"); dot.style.left = `${(pixel.x + .5) / element.naturalWidth * 100}%`; dot.style.top = `${(pixel.y + .5) / element.naturalHeight * 100}%`; layer.append(dot); });
  }

  async function updateOverlay() {
    if (!state.targetId || !$("science-overlay-visible").checked) { state.overlay = []; drawOverlay(); return; }
    const wavelength = Number($("science-wavelength").value), tolerance = Number($("science-tolerance").value);
    $("science-wavelength-label").textContent = `${number(wavelength, 3)} µm`;
    try {
      const result = await api(`/api/viewer/${encodeURIComponent(state.targetId)}/wavelength-overlay?wavelength_um=${encodeURIComponent(wavelength)}&tolerance_um=${encodeURIComponent(tolerance)}`);
      state.overlay = result.data.overlay.matching_pixels || []; drawOverlay();
      $("science-target-status").textContent = `${activeTarget().target_name} · ${result.data.overlay.matching_pixel_count} matching local-context pixels`;
    } catch (error) { state.overlay = []; drawOverlay(); $("science-target-status").textContent = `Overlay unavailable: ${error.message}`; }
  }

  async function updateOverlap() {
    const other = $("science-overlap-target").value;
    if (!other || !state.targetId) { $("science-overlap-status").textContent = "Select a second product to test cross-product wavelength-overlay support."; return; }
    try {
      const result = await api(`/api/viewer/${encodeURIComponent(state.targetId)}/overlap/${encodeURIComponent(other)}`);
      $("science-overlap-status").textContent = `${result.data.status}: ${result.data.message}`;
    } catch (error) { $("science-overlap-status").textContent = `Overlap check unavailable: ${error.message}`; }
  }

  async function selectPixel(event) {
    if (!state.targetId || state.drag || !image().naturalWidth) return;
    const point = imagePoint(event);
    try { panel((await api(`/api/viewer/${encodeURIComponent(state.targetId)}/pixel/${point.x}/${point.y}`)).data); }
    catch (error) { $("science-panel-data").textContent = `Pixel readout unavailable: ${error.message}`; $("science-panel").open = true; }
  }

  function populate(targets) {
    state.targets = targets;
    const options = targets.map(target => `<option value="${esc(target.target_id)}">${esc(target.target_name)} · ${esc(target.detector)}</option>`).join("");
    $("science-target").innerHTML = options;
    $("science-overlap-target").innerHTML = `<option value="">No second product</option>${options}`;
    loadTarget(targets[0].target_id);
  }

  image().addEventListener("load", () => fitToCanvas(true));
  $("science-canvas").addEventListener("wheel", event => { event.preventDefault(); state.zoom = Math.max(1, Math.min(16, state.zoom * (event.deltaY < 0 ? 1.15 : 1 / 1.15))); $("science-view-scale").textContent = `Fit ${number(state.fitScale, 1)}× · zoom ${number(state.zoom, 2)}×`; transform(); drawOverlay(); }, {passive:false});
  $("science-canvas").addEventListener("pointerdown", event => { state.drag = {x:event.clientX, y:event.clientY, panX:state.panX, panY:state.panY}; event.currentTarget.setPointerCapture(event.pointerId); });
  $("science-canvas").addEventListener("pointermove", event => { if (!state.drag) return; state.panX = state.drag.panX + event.clientX - state.drag.x; state.panY = state.drag.panY + event.clientY - state.drag.y; transform(); drawOverlay(); });
  $("science-canvas").addEventListener("pointerup", event => { const moved = state.drag && (Math.abs(event.clientX-state.drag.x) > 3 || Math.abs(event.clientY-state.drag.y) > 3); state.drag = null; if (!moved) selectPixel(event); });
  $("science-target").addEventListener("change", event => loadTarget(event.target.value));
  $("science-compare-target").addEventListener("click", () => document.dispatchEvent(new CustomEvent("cronoscope:load-local-target", {detail: {targetId: state.targetId}})));
  $("science-reset-view").addEventListener("click", resetView);
  $("science-overlap-target").addEventListener("change", updateOverlap);
  $("science-overlay-visible").addEventListener("change", updateOverlay);
  $("science-wavelength").addEventListener("input", updateOverlay);
  $("science-tolerance").addEventListener("change", updateOverlay);
  window.addEventListener("resize", () => fitToCanvas(false));
  api("/api/viewer/targets").then(result => populate(result.data.targets)).catch(error => { $("science-target-status").textContent = `Local viewer unavailable: ${error.message}`; });
})();
