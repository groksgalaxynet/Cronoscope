(() => {
  "use strict";

  const storageKey = "cronoscope.panel-state.v1";
  const panels = [
    ["target-gallery", "Target Gallery"],
    ["moving-explorer", "Moving Object Explorer"],
    ["genuine-spectrum", "Genuine SPHEREx Spectrum"],
    ["local-science-viewer", "SPHEREx Level-2 Science Image"],
    ["science-panel", "Science data panel"],
    ["search-panel", "Sky Search", true],
    ["viewer-panel", "Sky Viewer"],
    ["analysis-panel", "Comparison"],
  ];
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch { saved = {}; }

  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify(saved)); } catch { /* private browsing may disable storage */ }
  }

  function updateLanding() {
    const scientific = [...document.querySelectorAll("[data-panel-id]:not([data-essential-panel])")]
      .filter(panel => !panel.hidden);
    const landing = scientific.every(panel => panel.classList.contains("is-collapsed"));
    document.body.classList.toggle("landing-mode", landing);
    document.body.classList.toggle("workspace-mode", !landing);
  }

  function setCollapsed(panel, collapsed, save = true) {
    panel.classList.toggle("is-collapsed", collapsed);
    const button = panel.querySelector(":scope > .panel-collapse-heading > button");
    const body = panel.querySelector(":scope > .panel-collapse-body");
    if (button) {
      button.setAttribute("aria-expanded", String(!collapsed));
      button.setAttribute("aria-label", `${collapsed ? "Expand" : "Collapse"} ${panel.dataset.panelTitle}`);
      button.querySelector("span").textContent = collapsed ? "Expand" : "Collapse";
    }
    if (body) body.hidden = collapsed;
    if (save) { saved[panel.dataset.panelId] = collapsed; persist(); }
    updateLanding();
    if (!collapsed) requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
  }

  function preparePanel([id, title, essential = false]) {
    const panel = document.getElementById(id);
    if (!panel || panel.dataset.panelId) return;
    panel.dataset.panelId = id;
    panel.dataset.panelTitle = title;
    if (essential) panel.dataset.essentialPanel = "true";
    const body = document.createElement("div");
    body.className = "panel-collapse-body";
    body.id = `${id}-body`;
    while (panel.firstChild) body.append(panel.firstChild);
    const heading = document.createElement("div");
    heading.className = "panel-collapse-heading";
    const nested = Boolean(panel.parentElement?.closest("[data-panel-id]"));
    const toggleClass = nested ? "nested-panel-collapse-toggle" : "panel-collapse-toggle";
    heading.innerHTML = `<span class="panel-collapse-title">${title}</span><button class="${toggleClass} ghost" type="button" aria-controls="${body.id}"><span></span><span class="panel-collapse-icon" aria-hidden="true">⌄</span></button>`;
    panel.append(heading, body);
    heading.querySelector("button").addEventListener("click", () => setCollapsed(panel, !panel.classList.contains("is-collapsed")));
    // First visit: keep Sky Search ready; collapse the scientific workspaces.
    setCollapsed(panel, Object.hasOwn(saved, id) ? Boolean(saved[id]) : !essential, false);
    if (!Object.hasOwn(saved, id)) saved[id] = !essential;
  }

  function init() {
    const search = document.querySelector("main.workspace > .left");
    const viewer = document.querySelector("main.workspace > .viewer");
    const analysis = document.querySelector("main.workspace > .right");
    if (search) search.id = "search-panel";
    if (viewer) viewer.id = "viewer-panel";
    if (analysis) analysis.id = "analysis-panel";
    panels.forEach(preparePanel);
    persist();

    const video = document.getElementById("cronoscope-logo-video");
    const fallback = document.getElementById("cronoscope-logo-fallback");
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const showFallback = () => { if (video) { video.pause(); video.hidden = true; } if (fallback) fallback.hidden = false; };
    const useVideo = () => {
      if (!video || reduced.matches) return showFallback();
      video.hidden = false; fallback.hidden = true; video.muted = true; video.defaultMuted = true; video.volume = 0;
      video.play().catch(showFallback);
    };
    if (video) {
      video.muted = true; video.defaultMuted = true; video.volume = 0;
      video.addEventListener("error", showFallback, { once: true });
      video.addEventListener("loadeddata", useVideo, { once: true });
      useVideo();
    }
    reduced.addEventListener?.("change", useVideo);
    new MutationObserver(records => records.forEach(record => {
      if (record.attributeName === "hidden" && !record.target.hidden) setCollapsed(record.target, false);
      updateLanding();
    })).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["hidden"] });
    window.CronoscopePanels = { expand: id => { const panel = document.getElementById(id); if (panel) setCollapsed(panel, false); } };
    updateLanding();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
