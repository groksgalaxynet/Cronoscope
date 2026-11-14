(() => {
  "use strict";
  const key = "cronoscope.static-demo.panel-state.v1";
  const definitions = [["target-gallery", "Target Gallery"], ["judge-guide", "60-second guide"], ["workflow", "How it works"], ["featured", "Featured example"], ["tracks", "Moving Objects"], ["nasa-targets", "NASA Challenge Targets"], ["selected-track", "Selected track", true], ["observation-explorer", "Observation Explorer"], ["provenance", "Static science contract"]];
  let states = {}; try { states = JSON.parse(localStorage.getItem(key) || "{}"); } catch { states = {}; }
  const save = () => { try { localStorage.setItem(key, JSON.stringify(states)); } catch {} };
  function landing() { const panels = [...document.querySelectorAll("[data-static-panel]")].filter(panel => !panel.hidden && !panel.dataset.essential); document.body.classList.toggle("landing-mode", panels.every(panel => panel.classList.contains("is-collapsed"))); document.body.classList.toggle("workspace-mode", !document.body.classList.contains("landing-mode")); }
  function set(panel, collapsed, persist = true) { panel.classList.toggle("is-collapsed", collapsed); const button = panel.querySelector(":scope > .panel-collapse-heading button"), body = panel.querySelector(":scope > .panel-collapse-body"); button.setAttribute("aria-expanded", String(!collapsed)); button.querySelector("span").textContent = collapsed ? "Expand" : "Collapse"; body.hidden = collapsed; if (persist) { states[panel.id] = collapsed; save(); } landing(); if (!collapsed) requestAnimationFrame(() => window.dispatchEvent(new Event("resize"))); }
  function init() {
    document.querySelector(".workflow").id = "workflow";
    definitions.forEach(([id, title, essential]) => { const panel = document.getElementById(id); if (!panel) return; panel.dataset.staticPanel = "true"; if (essential) panel.dataset.essential = "true"; const body = document.createElement("div"); body.className = "panel-collapse-body"; body.id = `${id}-body`; while (panel.firstChild) body.append(panel.firstChild); const heading = document.createElement("div"); heading.className = "panel-collapse-heading"; heading.innerHTML = `<strong>${title}</strong><button class="panel-collapse-toggle" type="button" aria-controls="${body.id}"><span></span><i aria-hidden="true">⌄</i></button>`; panel.append(heading, body); heading.querySelector("button").onclick = () => set(panel, !panel.classList.contains("is-collapsed")); set(panel, Object.hasOwn(states, id) ? Boolean(states[id]) : !essential, false); });
    save();
    const video = document.getElementById("cronoscope-logo-video"), fallback = document.getElementById("cronoscope-logo-fallback"), reduced = matchMedia("(prefers-reduced-motion: reduce)");
    const fallbackOn = () => { video.pause(); video.hidden = true; fallback.hidden = false; };
    const play = () => { if (reduced.matches) return fallbackOn(); video.hidden = false; fallback.hidden = true; video.muted = video.defaultMuted = true; video.volume = 0; video.play().catch(fallbackOn); };
    video.addEventListener("error", fallbackOn, { once: true }); video.addEventListener("loadeddata", play, { once: true }); play(); reduced.addEventListener?.("change", play);
    new MutationObserver(records => records.forEach(record => { if (record.target.id === "observation-explorer" && !record.target.hidden) set(record.target, false); landing(); })).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["hidden"] });
    window.CronoscopeStaticPanels = { expand: id => { const panel = document.getElementById(id); if (panel) set(panel, false); } };
    landing();
  }
  init();
})();
