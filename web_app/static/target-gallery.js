(() => {
  "use strict";

  const GALLERY = {
    m31: {
      name: "M 31 · Andromeda Galaxy",
      image: "/static/assets/target-gallery/m31-hubble.jpg",
      alt: "Wide color Hubble mosaic of the Andromeda Galaxy, M31",
      source: "NASA Science · Hubble M31 PHAT+PHAST Mosaic",
      sourceUrl: "https://science.nasa.gov/asset/hubble/hubble-m31-phatphast-mosaic/",
      credit: "NASA, ESA, Benjamin Williams (UWashington), Zhuo Chen (UWashington), L. Clifton Johnson (Northwestern); image processing: Joseph DePasquale (STScI)",
      instrument: "Hubble Space Telescope ACS · F475W and F814W assigned-color composite",
    },
    m87: {
      name: "M 87 · Virgo A",
      image: "/static/assets/target-gallery/m87-hubble.jpg",
      alt: "Color Hubble view of elliptical galaxy M87 and its blue jet",
      source: "NASA Science · Black Hole-Powered Jet in Elliptical Galaxy M87",
      sourceUrl: "https://science.nasa.gov/image-detail/m87-full_jpg/",
      credit: "NASA, ESA and the Hubble Heritage Team (STScI/AURA); acknowledgment: P. Cote (Herzberg Institute of Astrophysics) and E. Baltz (Stanford University)",
      instrument: "Hubble Space Telescope · visible and infrared composite",
    },
    m42: {
      name: "M 42 · Orion Nebula",
      image: "/static/assets/target-gallery/m42-hubble.png",
      alt: "Color Hubble and ground-based mosaic of the Orion Nebula, M42",
      source: "NASA Science · Orion Nebula",
      sourceUrl: "https://science.nasa.gov/asset/hubble/orion-nebula-3/",
      credit: "NASA, ESA, Hubble Space Telescope Orion Treasury Project Team, Massimo Robberto (STScI, ESA)",
      instrument: "Hubble ACS and ESO MPI 2.2 m La Silla WFI · five-color visible/near-infrared mosaic",
    },
  };
  const MEDIA_GUIDELINES = "https://www.nasa.gov/nasa-brand-center/images-and-media/";
  const $ = id => document.getElementById(id);
  const stage = $("target-gallery-stage");
  const image = $("target-gallery-image");
  const placeholder = $("target-gallery-placeholder");
  const status = $("target-gallery-status");
  const attribution = $("target-gallery-attribution");
  const scaleOutput = $("target-gallery-scale");
  const controls = [$("target-gallery-zoom-out"), $("target-gallery-zoom-in"), $("target-gallery-reset")];
  const view = { scale: 1, x: 0, y: 0, revision: 0, pointerId: null, startX: 0, startY: 0, originX: 0, originY: 0 };

  function identify(resolution) {
    const value = `${resolution?.query || ""} ${resolution?.canonical_name || ""}`.toLowerCase();
    if (/\bm\s*31\b|andromeda|ngc\s*224\b/.test(value)) return GALLERY.m31;
    if (/\bm\s*87\b|virgo\s*a\b|ngc\s*4486\b/.test(value)) return GALLERY.m87;
    if (/\bm\s*42\b|orion\s*nebula|ngc\s*1976\b/.test(value)) return GALLERY.m42;
    return null;
  }

  function clampPan() {
    if (image.hidden) return;
    const maxX = Math.max(0, (image.offsetWidth * view.scale - stage.clientWidth) / 2);
    const maxY = Math.max(0, (image.offsetHeight * view.scale - stage.clientHeight) / 2);
    view.x = Math.max(-maxX, Math.min(maxX, view.x));
    view.y = Math.max(-maxY, Math.min(maxY, view.y));
  }

  function renderTransform() {
    clampPan();
    image.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
    scaleOutput.value = `${Math.round(view.scale * 100)}%`;
  }

  function resetView() {
    view.scale = 1; view.x = 0; view.y = 0;
    renderTransform();
  }

  function setScale(next) {
    view.scale = Math.max(1, Math.min(6, next));
    if (view.scale === 1) { view.x = 0; view.y = 0; }
    renderTransform();
  }

  function setControls(enabled) {
    controls.forEach(control => { control.disabled = !enabled; });
  }

  function clear(message = "No verified target image selected. Arbitrary coordinates are never matched to a photograph.") {
    ++view.revision;
    image.onload = null; image.onerror = null; image.removeAttribute("src"); image.hidden = true; image.alt = "";
    placeholder.hidden = false; placeholder.textContent = message;
    status.textContent = message;
    attribution.replaceChildren();
    const heading = document.createElement("h3"); heading.textContent = "Reference image details";
    const copy = document.createElement("p"); copy.textContent = "No external photograph is displayed without a verified target identity.";
    attribution.append(heading, copy);
    setControls(false); resetView();
  }

  function addDetail(list, term, value, link) {
    const dt = document.createElement("dt"); dt.textContent = term;
    const dd = document.createElement("dd");
    if (link) { const anchor = document.createElement("a"); anchor.href = link; anchor.target = "_blank"; anchor.rel = "noopener noreferrer"; anchor.textContent = value; dd.append(anchor); }
    else dd.textContent = value;
    list.append(dt, dd);
  }

  function renderAttribution(item) {
    attribution.replaceChildren();
    const heading = document.createElement("h3"); heading.textContent = "Reference image details";
    const list = document.createElement("dl");
    addDetail(list, "Target", item.name);
    addDetail(list, "Source", item.source, item.sourceUrl);
    addDetail(list, "Credit", item.credit);
    addDetail(list, "Imaging", item.instrument);
    addDetail(list, "Reuse", "NASA Images and Media Usage Guidelines", MEDIA_GUIDELINES);
    const warning = document.createElement("p"); warning.className = "reference-warning"; warning.textContent = "Color reference only — this image is not SPHEREx data, photometry, or a measurement product.";
    attribution.append(heading, list, warning);
  }

  function show(resolution) {
    const item = identify(resolution);
    clear(item ? `Loading verified reference image for ${item.name}…` : "Resolved target has no bundled reference photograph; no substitute is shown.");
    if (!item) return false;
    const revision = view.revision;
    image.alt = item.alt;
    image.onload = () => {
      if (revision !== view.revision) return;
      placeholder.hidden = true; image.hidden = false;
      status.textContent = `${item.name} · bundled color reference available offline.`;
      renderAttribution(item); setControls(true); resetView();
    };
    image.onerror = () => {
      if (revision !== view.revision) return;
      image.hidden = true; placeholder.hidden = false;
      placeholder.textContent = `The bundled image for ${item.name} is unavailable. No substitute is shown.`;
      status.textContent = placeholder.textContent; setControls(false);
    };
    image.src = item.image;
    return true;
  }

  $("target-gallery-zoom-in").addEventListener("click", () => setScale(view.scale * 1.25));
  $("target-gallery-zoom-out").addEventListener("click", () => setScale(view.scale / 1.25));
  $("target-gallery-reset").addEventListener("click", resetView);
  stage.addEventListener("wheel", event => {
    if (image.hidden) return;
    event.preventDefault();
    setScale(view.scale * (event.deltaY < 0 ? 1.15 : 1 / 1.15));
  }, { passive: false });
  stage.addEventListener("pointerdown", event => {
    if (image.hidden || view.scale <= 1) return;
    view.pointerId = event.pointerId; view.startX = event.clientX; view.startY = event.clientY; view.originX = view.x; view.originY = view.y;
    stage.setPointerCapture(event.pointerId); stage.classList.add("dragging");
  });
  stage.addEventListener("pointermove", event => {
    if (view.pointerId !== event.pointerId) return;
    view.x = view.originX + event.clientX - view.startX; view.y = view.originY + event.clientY - view.startY; renderTransform();
  });
  function endPan(event) {
    if (view.pointerId !== event.pointerId) return;
    view.pointerId = null; stage.classList.remove("dragging");
  }
  stage.addEventListener("pointerup", endPan); stage.addEventListener("pointercancel", endPan);
  window.addEventListener("resize", renderTransform);
  $("target-name").addEventListener("input", () => clear("Target name changed. Resolve it to verify the image identity."));
  for (const id of ["ra", "dec"]) $(id).addEventListener("input", () => clear("Coordinates were edited manually. Resolve a target name to verify an image identity."));

  window.CronoscopeTargetGallery = { clear, show, reset: resetView, identify };
})();
