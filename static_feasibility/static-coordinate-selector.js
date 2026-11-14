(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const precision = 0.00001;
  const halfLastDigit = precision / 2 + 1e-10;
  let catalog;

  const deltaRa = (left, right) => Math.abs(((left - right + 540) % 360) - 180);
  const endpointMatches = (coordinate, endpoint) =>
    deltaRa(coordinate.ra, endpoint.ra_deg) <= halfLastDigit &&
    Math.abs(coordinate.dec - endpoint.dec_deg) <= halfLastDigit;

  function status(message) { $("coordinate-status").textContent = message; }

  function validate(ra, dec) {
    if (!Number.isFinite(ra) || !Number.isFinite(dec)) return "Enter finite decimal-degree RA and Dec values.";
    if (ra < 0 || ra >= 360) return "RA must be at least 0° and less than 360°.";
    if (dec < -90 || dec > 90) return "Dec must be between −90° and +90°.";
    return null;
  }

  function selectMatch(match) {
    const button = document.querySelector(`#track-list [data-id="${match.track.id}"]`);
    if (!button) { status("The static catalog is still loading; try again in a moment."); return; }
    button.click();
    $("explore-observations").click();
    $("selected-track").scrollIntoView({ behavior: "smooth", block: "start" });
    const endpoint = match.role === "a" ? "earlier (A)" : "later (B)";
    status(`Matched ${match.track.label} at its documented ${endpoint} endpoint: ${match.track.observation_a}${match.role === "a" ? "" : ` → ${match.track.observation_b}`}. Available packaged observations are shown below.`);
  }

  $("coordinate-form").addEventListener("submit", event => {
    event.preventDefault();
    const coordinate = { ra: Number($("coordinate-ra").value), dec: Number($("coordinate-dec").value) };
    const issue = validate(coordinate.ra, coordinate.dec);
    if (issue) { status(issue); return; }
    if (!catalog) { status("The packaged catalog is still loading; try again in a moment."); return; }
    const match = catalog.tracks.flatMap(track => ["a", "b"].map(role => ({ track, role, endpoint: track[role] })))
      .find(candidate => endpointMatches(coordinate, candidate.endpoint));
    if (!match) {
      status("Unavailable: no retained packaged endpoint matches these coordinates. This offline demo does not search archive coverage or retrieve new imagery.");
      return;
    }
    selectMatch(match);
  });

  fetch("demo/catalog.json").then(response => response.json()).then(value => { catalog = value; })
    .catch(() => status("Packaged coordinate matching is unavailable because the local catalog could not be read."));
})();
