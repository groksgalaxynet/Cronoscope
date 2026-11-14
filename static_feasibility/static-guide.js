(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const messages = {
    target: "1 Target · RW Aurigae is selected from the packaged NASA Space Apps Challenge catalog. Its real two-epoch context and scientific status are shown below.",
    time: "2 Time · The timeline displays RW Aurigae’s two packaged SPHEREx observation epochs in their recorded UTC order.",
    compare: "3 Compare · Epoch A and Epoch B are available as packaged images. Blink alternates those existing views; no new registration or scientific processing is performed.",
    wavelength: "4 Wavelength · RW Aurigae’s packaged D3 wavelength context and genuine forced-photometry spectrum are displayed with their supplied units and provenance.",
  };
  const expand = id => window.CronoscopeStaticPanels?.expand(id);
  const scroll = id => $(id)?.scrollIntoView({ behavior: "smooth", block: "center" });
  function rwButton() { return document.querySelector('#nasa-target-list [data-nasa-id="rw-aur"]'); }
  function selectRw() { const target = rwButton(); if (!target) return false; target.click(); expand("selected-track"); return true; }
  function openExplorer() { if (!selectRw()) return false; $("explore-observations").click(); expand("observation-explorer"); return true; }
  function activate(step) {
    if (!rwButton()) return;
    $("judge-guide").hidden = false; $("guide-show").hidden = true;
    $("guide-message").textContent = messages[step];
    document.querySelectorAll("#guide-steps [data-guide]").forEach(button => {
      const active = button.dataset.guide === step;
      button.classList.toggle("active", active);
      button.toggleAttribute("aria-current", active);
    });
    if (step === "target") { selectRw(); scroll("selected-track"); return; }
    if (!openExplorer()) return;
    if (step === "time") { scroll("observation-timeline"); return; }
    if (step === "compare") { document.querySelector('#view-controls [data-view="a"]')?.click(); scroll("view-controls"); return; }
    if (step === "wavelength") { document.querySelector('#view-controls [data-view="spectrum"]')?.click(); scroll("spectral-explorer"); }
  }
  document.addEventListener("click", event => {
    const button = event.target.closest("#guide-steps [data-guide], #guide-restart");
    if (!button) return;
    event.preventDefault(); event.stopImmediatePropagation();
    activate(button.id === "guide-restart" ? "target" : button.dataset.guide);
  }, true);
})();
