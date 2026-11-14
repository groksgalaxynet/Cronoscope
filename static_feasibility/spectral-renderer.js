/* Browser-native rendering of exported genuine SPHEREx forced photometry. */
(() => {
  const number = value => {
    if ((typeof value !== "number" && typeof value !== "string") || (typeof value === "string" && !value.trim())) return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  };
  const esc = value => String(value ?? "—").replace(/[&<>]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[char]));
  const extent = values => { const finite = values.filter(Number.isFinite); const low = Math.min(...finite), high = Math.max(...finite); return [low, high === low ? low + 1 : high]; };
  const detectorColor = detector => ({1:"#9b8cff",2:"#42d8ff",3:"#6ce5b1",4:"#ffd36f",5:"#ff8fd1",6:"#ff9e7b"})[detector] || "#c8dced";
  const fluxText = value => { const numeric = number(value), absolute = Math.abs(numeric ?? 0); if (numeric === null) return "unavailable"; return absolute >= 1e7 ? numeric.toExponential(3) : absolute >= 1e4 ? numeric.toLocaleString(undefined, {maximumFractionDigits:0}) : numeric.toFixed(3); };
  const mjdDate = value => new Date((Number(value) - 40587) * 86400000).toLocaleString(undefined, {month:"short", day:"numeric", year:"numeric", timeZoneName:"short"});
  const REVIEW_CLASSES = new Set(["USABLE", "CAUTION", "EXCLUDE", "UNREVIEWED"]);
  const DOCUMENTED_FLAGS = new Map([[0n,"TRANSIENT"],[1n,"OVERFLOW"],[2n,"SUR_ERROR"],[6n,"NONFUNC"],[7n,"DICHROIC"],[9n,"MISSING_DATA"],[10n,"HOT"],[32n,"CONTAINS_BAD_PIXEL"],[33n,"FIT_ERROR"]]);
  const MAX_FLAG = (1n << 64n) - 1n;
  const exactFlag = value => {
    if (typeof value === "bigint") return value >= 0n && value <= MAX_FLAG ? value : null;
    if (typeof value === "number") return Number.isSafeInteger(value) && value >= 0 ? BigInt(value) : null;
    if (typeof value === "string" && /^\d+$/.test(value.trim())) { try { const parsed = BigInt(value.trim()); return parsed <= MAX_FLAG ? parsed : null; } catch (_) { return null; } }
    return null;
  };
  const decodeFlags = value => {
    if (value === null || value === undefined || value === "") return {state:"absent", value:null, documented:[], undocumented:[]};
    const flags = exactFlag(value);
    if (flags === null) return {state:"unsafe", value:null, documented:[], undocumented:[]};
    const documented = [], undocumented = []; let remaining = flags, bit = 0n;
    while (remaining) { if (remaining & 1n) { const label = DOCUMENTED_FLAGS.get(bit); if (label) documented.push(label); else undocumented.push(bit.toString()); } remaining >>= 1n; bit += 1n; }
    return {state:"exact", value:flags, documented, undocumented};
  };
  const reviewClass = row => { const value = String(row?.review_classification ?? row?.scientific_quality ?? "UNREVIEWED").trim().toUpperCase(); return REVIEW_CLASSES.has(value) ? value : "UNREVIEWED"; };
  const warningMessages = (row, flags = decodeFlags(row?.quality_flags)) => {
    const warnings = [];
    if (flags.state === "unsafe") warnings.push("This measurement has a quality flag that is not an exact non-negative integer, so it cannot be decoded safely.");
    if (flags.documented.includes("CONTAINS_BAD_PIXEL")) warnings.push("This measurement contains a bad-pixel warning. Its flux may be affected.");
    if (flags.documented.includes("DICHROIC")) warnings.push("This measurement is in a region with additional calibration uncertainty.");
    if (flags.documented.includes("FIT_ERROR")) warnings.push("This measurement reports a fit error. Its fitted flux may not have converged.");
    if (flags.undocumented.length) warnings.push("This measurement contains quality flags whose meanings are not documented in the available reference (bits " + flags.undocumented.join(", ") + ").");
    const fit = number(row?.fit_quality);
    if (fit !== null && fit > 1) warnings.push("The fitted model has substantial residuals relative to pixel uncertainties. Interpret this flux cautiously.");
    if (reviewClass(row) === "UNREVIEWED") warnings.push("This measurement has not received a scientific-quality review. Its reliability has not been established.");
    if (number(row?.flux_uncertainty) === null) warnings.push("Flux uncertainty is unavailable. No error bar is shown.");
    return warnings;
  };

  function spectralSvg(rows, {xKey, xLabel, title, selectedIndex, time = false, scale = "log"}) {
    const finite = rows.filter(row => number(row[xKey]) !== null && number(row.flux_density) !== null);
    const shown = scale === "log" ? finite.filter(row => number(row.flux_density) > 0) : finite;
    if (!shown.length) return '<p class="spectral-empty">No measurements can be displayed with this axis scale.</p>';
    const W = 760, H = 330, L = 72, R = 18, T = 28, B = 52, xs = extent(shown.map(row => number(row[xKey]))), values = shown.map(row => number(row.flux_density)), ys = scale === "log" ? extent(values.map(Math.log10)) : extent(values);
    const sx = value => L + (number(value) - xs[0]) / (xs[1] - xs[0]) * (W - L - R);
    const sy = value => { const rendered = scale === "log" ? Math.log10(Math.max(number(value), Number.MIN_VALUE)) : number(value); return H - B - (rendered - ys[0]) / (ys[1] - ys[0]) * (H - B - T); };
    const clip = value => Math.max(T, Math.min(H - B, value));
    const tick = value => { const absolute = Math.abs(value); return absolute >= 1e7 ? value.toExponential(2) : absolute >= 1e6 ? `${(value / 1e6).toFixed(2)}M` : absolute >= 1e3 ? `${(value / 1e3).toFixed(0)}k` : absolute > 0 && absolute < .01 ? value.toExponential(2) : value.toFixed(0); };
    const points = shown.map(row => { const value = number(row.flux_density), x = sx(row[xKey]), y = sy(value), uncertainty = number(row.flux_uncertainty), low = uncertainty === null ? y : clip(sy(scale === "log" ? Math.max(Number.MIN_VALUE, value - uncertainty) : value - uncertainty)), high = uncertainty === null ? y : clip(sy(value + uncertainty)), flags = decodeFlags(row.quality_flags), flagged = flags.state === "unsafe" || (flags.value !== null && flags.value !== 0n), review = reviewClass(row); const label = `${row.wavelength_um?.toFixed(6)} µm; ${fluxText(value)} ${row.flux_unit}; uncertainty ${fluxText(uncertainty)}; MJD ${number(row.observation_mjd)?.toFixed(6)}; detector ${row.detector}; flags ${row.quality_flags}; review ${review}`; return `<g><line class="spectral-error" x1="${x}" x2="${x}" y1="${low}" y2="${high}"/><circle class="spectral-point det-${esc(row.detector)} ${flagged ? "flagged" : ""} review-${review.toLowerCase()} ${row._index === selectedIndex ? "selected" : ""}" data-spectral-row="${row._index}" cx="${x}" cy="${y}" r="${row._index === selectedIndex ? 5 : 3.25}" tabindex="0" role="button" aria-label="${esc(label)}"><title>${esc(label)}</title></circle></g>`; }).join("");
    const yTitle = `Flux density (${esc(shown[0].flux_unit)}, ${scale} scale)`;
    return `<svg class="spectral-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}"><text x="${L}" y="17" fill="#edf5ff" font-size="13">${esc(title)}</text><line class="spectral-axis" x1="${L}" y1="${H-B}" x2="${W-R}" y2="${H-B}"/><line class="spectral-axis" x1="${L}" y1="${T}" x2="${L}" y2="${H-B}"/><text x="${L}" y="${H-18}" fill="#9cb3cb" font-size="11">${time ? `MJD ${xs[0].toFixed(2)} (${mjdDate(xs[0])})` : `${xs[0].toFixed(3)} µm`}</text><text x="${W-R}" y="${H-18}" fill="#9cb3cb" font-size="11" text-anchor="end">${time ? `MJD ${xs[1].toFixed(2)} (${mjdDate(xs[1])})` : `${xs[1].toFixed(3)} µm`}</text><text x="${L-8}" y="${T+5}" fill="#9cb3cb" font-size="11" text-anchor="end">${tick(scale === "log" ? 10 ** ys[1] : ys[1])}</text><text x="${L-8}" y="${H-B}" fill="#9cb3cb" font-size="11" text-anchor="end">${tick(scale === "log" ? 10 ** ys[0] : ys[0])}</text><text x="${(L+W-R)/2}" y="${H-3}" fill="#9cb3cb" font-size="11" text-anchor="middle">${esc(xLabel)}</text><text x="14" y="${(T+H-B)/2}" fill="#9cb3cb" font-size="11" transform="rotate(-90 14 ${(T+H-B)/2})" text-anchor="middle">${yTitle}</text>${points}</svg>`;
  }

  function comparableGroups(rows) {
    const groups = {};
    rows.filter(row => row.usable && number(row.wavelength_um) !== null && number(row.observation_mjd) !== null && number(row.wavelength_width_um) !== null).forEach(row => (groups[`D${row.detector} · ${row.processing_release}`] ??= []).push(row));
    return Object.entries(groups).flatMap(([name, rows]) => { rows.sort((a, b) => (a.wavelength_um - a.wavelength_width_um / 2) - (b.wavelength_um - b.wavelength_width_um / 2)); let cluster = [], low, high; const finish = () => { const times = cluster.map(row => row.observation_mjd), observations = new Set(cluster.map(row => row.observation_id).filter(Boolean)); const result = cluster.length >= 2 && observations.size >= 2 && Math.max(...times) - Math.min(...times) >= 1 ? [{key:`${name}|${low.toFixed(5)}|${high.toFixed(5)}`, label:`${name} · shared ${low.toFixed(4)}–${high.toFixed(4)} µm · ${cluster.length} measurements`, rows:[...cluster]}] : []; return result; }; const output = []; rows.forEach(row => { const rowLow = row.wavelength_um - row.wavelength_width_um / 2, rowHigh = row.wavelength_um + row.wavelength_width_um / 2, nextLow = cluster.length ? Math.max(low, rowLow) : rowLow, nextHigh = cluster.length ? Math.min(high, rowHigh) : rowHigh; if (nextLow <= nextHigh) { cluster.push(row); low = nextLow; high = nextHigh; } else { output.push(...finish()); cluster = [row]; low = rowLow; high = rowHigh; } }); output.push(...finish()); return output; }).sort((a, b) => a.label.localeCompare(b.label));
  }

  function render(container, data) {
    const state = container.__cronoscopeSpectrumState ??= {target:null, scale:"log", selected:null, group:null, noGroup:false};
    if (state.target !== data?.spectrum_id) { state.target = data?.spectrum_id; state.scale = data?.spectrum_id === "r-draconis" ? "linear" : "log"; state.selected = state.group = null; state.noGroup = false; }
    const rows = (data?.measurements || []).map((row, index) => ({...row, _index:index})), usable = rows.filter(row => row.usable && number(row.wavelength_um) !== null && number(row.flux_density) !== null);
    if (!usable.length) { container.innerHTML = '<p class="spectral-empty"><b>Spectral data unavailable.</b> No verified spectral measurements are available for this target.</p>'; return; }
    const groups = comparableGroups(usable), displayed = state.scale === "log" ? usable.filter(row => number(row.flux_density) > 0) : usable, nonpositive = usable.filter(row => number(row.flux_density) <= 0), selected = rows.find(row => row._index === state.selected), selectedGroup = selected && groups.find(group => group.rows.some(row => row._index === selected._index));
    if (selected) { state.group = selectedGroup?.key || null; state.noGroup = !selectedGroup; }
    const active = state.noGroup ? null : groups.find(group => group.key === state.group) || groups[0];
    state.group = active?.key || null;
    const selectedFlags = selected ? decodeFlags(selected.quality_flags) : null, selectedReview = selected ? reviewClass(selected) : null, selectedWarnings = selected ? warningMessages(selected, selectedFlags) : [];
    const detail = selected ? `<div class="spectral-detail"><b>Selected measurement</b><br>${selected.wavelength_um.toFixed(6)} µm · ${fluxText(selected.flux_density)} ${esc(selected.flux_unit)} ± ${fluxText(selected.flux_uncertainty)} ${esc(selected.flux_uncertainty_unit)}<br>MJD ${selected.observation_mjd?.toFixed(6)} (${mjdDate(selected.observation_mjd)}) · detector ${esc(selected.detector)} · ${esc(selected.processing_release)} · flags ${esc(selected.quality_flags)}<br><b>Scientific review: ${esc(selectedReview)}</b><br>Fit quality: ${number(selected.fit_quality) === null ? "Fit-quality information unavailable." : `${number(selected.fit_quality).toPrecision(6)}. IRSA describes values near 1 as favorable; larger values can indicate fitting problems.`}<br>${selectedWarnings.length ? `<b>Warnings</b><ul>${selectedWarnings.map(message => `<li>${esc(message)}</li>`).join("")}</ul>` : "<b>Warnings</b><br>No documented display warning is triggered for this measurement."}</div>` : '<p class="spectral-note">Select a point for wavelength, signed flux, uncertainty, MJD, detector, release, raw flags, review status, and fit quality.</p>';
    const unavailableComparison = selected ? `Selected detector ${esc(selected.detector)} / ${esc(selected.processing_release)} measurement has no scientifically comparable multi-date wavelength interval. The previous comparison is not shown.` : "No comparable multi-date interval is available.";
    const reviewCounts = ["USABLE", "CAUTION", "EXCLUDE", "UNREVIEWED"].map(kind => `${usable.filter(row => reviewClass(row) === kind).length} ${kind}`).join(" · ");
    container.innerHTML = `<p class="eyebrow">Genuine SPHEREx Spectrum · forced photometry</p><h3>${esc(data.target_id)}</h3><div class="spectral-meta"><span>${rows.length} extracted records</span><span>${usable.length} finite wavelength/flux rows</span><span>${usable.filter(row => { const flags = decodeFlags(row.quality_flags); return flags.state === "unsafe" || (flags.value !== null && flags.value !== 0n); }).length} flagged rows</span><span>${reviewCounts}</span><span>${Math.min(...usable.map(row => row.wavelength_um)).toFixed(6)}–${Math.max(...usable.map(row => row.wavelength_um)).toFixed(6)} µm</span></div><p class="spectral-note spectral-display-note">Overview plots every finite measurement. Linear mode preserves signed flux; logarithmic mode improves extreme-value readability but omits nonpositive values.</p><p class="spectral-note">These are genuine SPHEREx forced-photometry measurements. This graph does not interpolate missing spectral values or represent the WCS-WAVE wavelength map.</p><p class="spectral-note">Source: ${esc(data.source_provenance)} · ${esc(data.extraction_method)}</p><div class="spectral-legend">${[1,2,3,4,5,6].map(detector => `<span><b style="background:${detectorColor(String(detector))}"></b>D${detector}</span>`).join("")}<span>Outlined/faded markers = nonzero quality flags; review labels are textual and not an IRSA category.</span></div><div class="spectral-controls"><label>Flux axis scale<select data-spectrum-scale><option value="linear" ${state.scale === "linear" ? "selected" : ""}>Linear · all finite signed values</option><option value="log" ${state.scale === "log" ? "selected" : ""}>Logarithmic · positive values only</option></select></label></div>${spectralSvg(displayed, {xKey:"wavelength_um", xLabel:"Wavelength (µm)", title:`Flux density versus wavelength · ${state.scale} display`, selectedIndex:state.selected, scale:state.scale})}${state.scale === "log" && nonpositive.length ? `<p class="spectral-note">Logarithmic display omits ${nonpositive.length} zero or negative finite flux measurement${nonpositive.length === 1 ? "" : "s"}; they remain available in Linear view.</p>` : '<p class="spectral-note">Linear display retains signed, zero, and positive finite flux measurements. Negative fitted flux is not negative emitted light.</p>'}${detail}<hr><h3>Comparable light over time</h3>${active ? spectralSvg(active.rows, {xKey:"observation_mjd", xLabel:"Observation time (MJD)", title:active.label, selectedIndex:state.selected, time:true, scale:state.scale}) : `<p class="spectral-empty">${unavailableComparison}</p>`}`;
    container.querySelector("[data-spectrum-scale]").onchange = event => { state.scale = event.target.value; render(container, data); };
    container.querySelectorAll("[data-spectral-row]").forEach(node => { const select = () => { state.selected = Number(node.dataset.spectralRow); render(container, data); }; node.onclick = select; node.onkeydown = event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); } }; });
  }
  window.CronoscopeSpectralRenderer = {number, decodeFlags, reviewClass, warningMessages, spectralSvg, render};
})();
