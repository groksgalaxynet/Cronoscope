(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const details = {
    "barnards-star": { detector: "D3 · 1.6301–2.4346 µm", release: "SPHEREx Quick Release 2", classification: "Derived static PNG display from retained SPHEREx Level-2 cutout", source: "NASA_TARGET_FITS_INVENTORY.md" },
    "rw-aur": { detector: "D3 · 1.6301–2.4346 µm", release: "SPHEREx Quick Release 2", classification: "Derived static PNG display from retained SPHEREx Level-2 cutout", source: "NASA_TARGET_FITS_INVENTORY.md" },
    "r-draconis": { detector: "D3 · 1.6301–2.4346 µm", release: "SPHEREx Quick Release 2", classification: "Derived static PNG display from retained SPHEREx Level-2 cutout", source: "NASA_TARGET_FITS_INVENTORY.md" },
    "wise-0855": { detector: "D6 · 4.4115–5.0096 µm", release: "SPHEREx Quick Release 2", classification: "Derived static PNG display from retained SPHEREx Level-2 cutout", source: "NASA_TARGET_FITS_INVENTORY.md" },
  };
  let panel;
  const selected = () => document.querySelector("#nasa-target-list [data-nasa-id].active");
  const clear = () => { if (panel) panel.remove(); panel = null; };
  const render = () => {
    const button = selected(); const target = button && details[button.dataset.nasaId];
    clear();
    if (!target) return;
    const name = $("selected-name").textContent;
    const timeline = $("observation-timeline").innerText.replace(/\s+/g, " ").trim();
    const imageAvailable = !$("science-frame").hidden && $("science-image").hasAttribute("src");
    panel = document.createElement("section"); panel.id = "static-provenance-detail"; panel.className = "facts static-provenance-detail";
    panel.innerHTML = `<div><b>SPHEREx image provenance</b><span>${imageAvailable ? "Packaged static display" : "No display asset active"}</span><small>Target: ${name}. Mission: SPHEREx. ${timeline}</small></div><div><b>Detector / band</b><span>${target.detector}</span><small>Data release: ${target.release}. Source inventory: ${target.source}.</small></div><div><b>Data classification</b><span>${target.classification}</span><small>WCS-WAVE provides wavelength context only; it is not a source spectrum. Measured flux appears only in the separately labelled packaged spectral explorer.</small></div><div><b>Difference status</b><span>Unavailable for this NASA-target image pair</span><small>No validated registered difference product is packaged. A browser-derived difference is intentionally not generated; these images do not establish a detection or change claim.</small></div>`;
    $("wavelength-detail").insertAdjacentElement("afterend", panel);
  };
  new MutationObserver(render).observe($("nasa-target-list"), { subtree: true, attributes: true, attributeFilter: ["class"] });
  new MutationObserver(render).observe($("science-image"), { attributes: true, attributeFilter: ["src"] });
  new MutationObserver(render).observe($("observation-timeline"), { childList: true, subtree: true });
  render();
})();
