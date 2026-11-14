# NASA target static integration

## Changed

- `static_feasibility/index.html` — adds a NASA Challenge Targets selection group.
- `static_feasibility/app.js` — preserves the asteroid explorer and adds NASA-target selection, two-epoch viewing, blink, status language, and the imagery-pending panel.
- `static_feasibility/demo/nasa-targets.json` — static metadata for all five requested targets.
- `static_feasibility/demo/nasa-*.png` — eight browser PNG assets generated from owner-supplied FITS data.
- `nasa_targets/generate_static_nasa_assets.py` — repeatable read-only asset generator.

## Availability

- **Interactive A/B + Blink:** Barnard's Star, RW Aurigae, R Draconis, WISE 0855.
- **Context only:** Barnard's Star and RW Aurigae; neither claims measured motion or variability.
- **Invalid target pixels:** R Draconis.
- **Low signal-to-noise:** WISE 0855.
- **Imagery pending:** Epsilon Indi B; no image is substituted.

All imagery is packaged PNG only; the website makes no archive/API requests and includes no original FITS files. Existing asteroid records and assets remain unchanged.

## Local launch

From the project root, run:

```bash
./.venv/bin/python -m http.server 8012 --directory static_feasibility
```

Then open `http://127.0.0.1:8012`.
