(() => {
  "use strict";
  function openRwAurigae(event) {
    event.preventDefault(); event.stopImmediatePropagation();
    const target = document.querySelector('#nasa-target-list [data-nasa-id="rw-aur"]');
    if (!target) return;
    target.click();
    document.getElementById("explore-observations").click();
  }
  document.addEventListener("click", event => {
    if (event.target.closest("#explore-featured, #explore-featured-inline")) openRwAurigae(event);
  }, true);
})();
