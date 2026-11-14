(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const stage = $("science-image-stage"), image = $("science-image"), tools = $("science-image-tools");
  const scaleOutput = $("science-image-scale");
  const view = { scale: 1, x: 0, y: 0, pointer: null, startX: 0, startY: 0, originX: 0, originY: 0, source: null };
  const render = () => { image.style.transform = `translate(${view.x}px,${view.y}px) scale(${view.scale})`; scaleOutput.value = `${Math.round(view.scale * 100)}%`; };
  const reset = () => { view.scale = 1; view.x = view.y = 0; render(); };
  const active = () => !$("science-frame").hidden && image.hasAttribute("src");
  const refresh = () => { if (image.getAttribute("src") !== view.source) { view.source = image.getAttribute("src"); reset(); } tools.hidden = !active(); };

  $("science-image-zoom-in").onclick = () => { if (!active()) return; view.scale = Math.min(6, view.scale * 1.25); render(); };
  $("science-image-zoom-out").onclick = () => { if (!active()) return; view.scale = Math.max(1, view.scale / 1.25); if (view.scale === 1) view.x = view.y = 0; render(); };
  $("science-image-reset").onclick = reset;
  stage.addEventListener("wheel", event => { if (!active()) return; event.preventDefault(); view.scale = Math.max(1, Math.min(6, view.scale * (event.deltaY < 0 ? 1.15 : 1 / 1.15))); render(); }, { passive: false });
  stage.addEventListener("pointerdown", event => { if (!active() || view.scale <= 1) return; view.pointer = event.pointerId; view.startX = event.clientX; view.startY = event.clientY; view.originX = view.x; view.originY = view.y; stage.setPointerCapture(event.pointerId); });
  stage.addEventListener("pointermove", event => { if (view.pointer !== event.pointerId) return; view.x = view.originX + event.clientX - view.startX; view.y = view.originY + event.clientY - view.startY; render(); });
  stage.addEventListener("pointerup", event => { if (view.pointer === event.pointerId) view.pointer = null; });
  new MutationObserver(refresh).observe(image, { attributes: true, attributeFilter: ["src"] });
  new MutationObserver(refresh).observe($("science-frame"), { attributes: true, attributeFilter: ["hidden"] });
  refresh();
})();
