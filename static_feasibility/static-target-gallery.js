(() => {
  "use strict";
  const entries = {
    m31: { aliases: /\bm\s*31\b|andromeda|ngc\s*224/i, name: "M 31 · Andromeda Galaxy", image: "assets/target-gallery/m31-hubble.jpg", credit: "NASA, ESA, Benjamin Williams (UWashington), Zhuo Chen (UWashington), L. Clifton Johnson (Northwestern); image processing: Joseph DePasquale (STScI)", instrument: "Hubble Space Telescope ACS · assigned-color composite" },
    m87: { aliases: /\bm\s*87\b|virgo\s*a|ngc\s*4486/i, name: "M 87 · Virgo A", image: "assets/target-gallery/m87-hubble.jpg", credit: "NASA, ESA and the Hubble Heritage Team (STScI/AURA)", instrument: "Hubble Space Telescope · visible and infrared composite" },
    m42: { aliases: /\bm\s*42\b|orion\s*nebula|ngc\s*1976/i, name: "M 42 · Orion Nebula", image: "assets/target-gallery/m42-hubble.png", credit: "NASA, ESA, Hubble Space Telescope Orion Treasury Project Team", instrument: "Hubble ACS and ESO MPI 2.2 m La Silla WFI mosaic" },
  };
  const $ = id => document.getElementById(id);
  const image = $("target-gallery-image"), placeholder = $("target-gallery-placeholder"), stage = $("target-gallery-stage");
  const status = $("target-gallery-status"), attribution = $("target-gallery-attribution"), scale = $("target-gallery-scale");
  const controls = [$("target-gallery-zoom-out"), $("target-gallery-zoom-in"), $("target-gallery-reset")];
  const view = { scale: 1, x: 0, y: 0, pointer: null, startX: 0, startY: 0, originX: 0, originY: 0 };
  const matchGallery = query => Object.values(entries).find(entry => entry.aliases.test(query));
  const render = () => { image.style.transform = `translate(${view.x}px,${view.y}px) scale(${view.scale})`; scale.value = `${Math.round(view.scale * 100)}%`; };
  const reset = () => { view.scale = 1; view.x = view.y = 0; render(); };
  const enable = active => controls.forEach(control => { control.disabled = !active; });
  function clear(message) { image.hidden = true; image.removeAttribute("src"); placeholder.hidden = false; placeholder.textContent = message; status.textContent = message; enable(false); reset(); }
  function show(entry) {
    if (!entry) return clear("This packaged target has no verified bundled reference photograph. No substitute is shown.");
    clear(`Loading verified reference image for ${entry.name}…`);
    image.alt = `Color reference image of ${entry.name}`;
    image.onload = () => { image.hidden = false; placeholder.hidden = true; status.textContent = `${entry.name} · bundled color reference available offline.`; attribution.innerHTML = `<h3>Reference image details</h3><dl><dt>Target</dt><dd>${entry.name}</dd><dt>Credit</dt><dd>${entry.credit}</dd><dt>Imaging</dt><dd>${entry.instrument}</dd></dl><p class="reference-warning">Color reference only — not SPHEREx data, photometry, or a measurement product.</p>`; enable(true); reset(); };
    image.onerror = () => clear(`The bundled image for ${entry.name} is unavailable. No substitute is shown.`);
    image.src = entry.image;
  }
  $("target-gallery-zoom-in").onclick = () => { view.scale = Math.min(6, view.scale * 1.25); render(); };
  $("target-gallery-zoom-out").onclick = () => { view.scale = Math.max(1, view.scale / 1.25); if (view.scale === 1) view.x = view.y = 0; render(); };
  $("target-gallery-reset").onclick = reset;
  stage.addEventListener("wheel", event => { if (image.hidden) return; event.preventDefault(); view.scale = Math.max(1, Math.min(6, view.scale * (event.deltaY < 0 ? 1.15 : 1 / 1.15))); render(); }, { passive: false });
  stage.addEventListener("pointerdown", event => { if (image.hidden || view.scale <= 1) return; view.pointer = event.pointerId; view.startX = event.clientX; view.startY = event.clientY; view.originX = view.x; view.originY = view.y; stage.setPointerCapture(event.pointerId); });
  stage.addEventListener("pointermove", event => { if (view.pointer !== event.pointerId) return; view.x = view.originX + event.clientX - view.startX; view.y = view.originY + event.clientY - view.startY; render(); });
  stage.addEventListener("pointerup", event => { if (view.pointer === event.pointerId) view.pointer = null; });
  async function search() {
    const query = $("static-target-query").value.trim(); const output = $("static-target-status");
    if (!query) { output.textContent = "Enter one of the packaged target names or IDs."; return; }
    const gallery = matchGallery(query); if (gallery) { show(gallery); window.CronoscopeStaticPanels?.expand("target-gallery"); $("target-gallery").scrollIntoView({ behavior: "smooth", block: "start" }); output.textContent = `${gallery.name}: reference image available; no static SPHEREx observation is implied.`; return; }
    const buttons = [...document.querySelectorAll("#track-list [data-id], #nasa-target-list [data-nasa-id]")];
    const normalized = query.toLowerCase().replace(/\s+/g, " ");
    const button = buttons.find(node => node.textContent.toLowerCase().includes(normalized));
    if (button) { button.click(); $("selected-track").scrollIntoView({ behavior: "smooth", block: "start" }); output.textContent = `${button.textContent.trim().split("\n")[0]} is available in this packaged static catalog.`; return; }
    show(null); output.textContent = "Unavailable: this offline demo contains no matching packaged target or verified reference image.";
  }
  $("static-target-search").onclick = search;
  $("static-target-query").addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); search(); } });
  window.CronoscopeStaticGallery = { show, clear };
})();
