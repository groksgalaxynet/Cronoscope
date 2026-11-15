# Experimental DR1 Cube Service

This localhost-only WSGI service exposes the verified bounded cube reader under
`POST /api/experimental/dr1/cube/sample`. It is isolated from Cronoscope's
production routes and browser viewer.

By default it replays preserved genuine DR1.5 response ranges and makes zero
archive requests. Start it from the repository root with a private state
directory:

```bash
.venv/bin/python -m research.dr1_cube_service.api --state-dir /tmp/cronoscope-dr16-state
```

Open the experimental explorer at
<http://127.0.0.1:8766/experimental/dr1-cube>. The page and API are served by
the same localhost process; no production route or GitHub Pages asset is
changed.

Example request:

```bash
curl --fail-with-body -H 'Content-Type: application/json' \
  --data '{"product_id":"Npix7945_cube","channel":20,"x":90,"y":107,"width":4,"height":4}' \
  http://127.0.0.1:8766/api/experimental/dr1/cube/sample
```

Only `Npix7945_cube` is allowlisted. Clients cannot supply URLs, paths,
experiment IDs, budgets, cache locations, or concurrency limits. Channels 51
and 52 are unavailable, regions are limited to 32×32, request bodies are
limited to 4096 bytes, and exactly one retrieval may execute at a time.

Live archive mode exists only for separately authorized local research and is
disabled by default. It uses the exact allowlisted HTTPS URL, forbids redirects,
persists a fixed 40-attempt/16-MiB ledger, and never performs an unbounded GET.

IMAGE is coadded surface brightness in the genuine FITS unit. NHITS is
contribution count, not uncertainty. FLAGS are raw uninterpreted integers.
Cube samples are not source photometry, calibrated source spectra, observation
epochs, motion detections, or variability measurements. Decoder agreement is
not independent photometric calibration.
