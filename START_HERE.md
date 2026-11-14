# Start here: Cronoscope

Cronoscope is an evidence-first astronomy exploration project. It combines
genuine SPHEREx observation context, celestial coordinates, wavelength
context, and observations made at different times while keeping the limits of
the evidence visible.

Cronoscope has two separate experiences:

| Experience | What it provides | What it does not provide |
| --- | --- | --- |
| **Static demonstration** | A self-contained browser experience with labelled packaged displays, target switching, frozen coordinate matching, observation views, blink, provenance, and an illustrative gallery | Live archive requests, FITS-pixel measurement, arbitrary sky searches, or automatic discovery claims |
| **Full Python application** | Local FITS/WCS/WCS-WAVE inspection, pixel/quality context, and bounded comparison workflows when appropriate FITS products are available locally | A bundled offline archive or a complete DR1 integration |

## Clone the project

```bash
git clone https://github.com/groksgalaxynet/Cronoscope.git
cd Cronoscope
```

The public competition release contains `static_feasibility/`, `web_app/`,
`cronoscope_pipeline/`, dependency manifests, licensing, and provenance
documentation. It intentionally does not include retained local FITS products,
research caches, or private development artifacts.

## Static demonstration

The static demonstration is the quickest way to explore Cronoscope. It needs
no Python scientific dependencies, credentials, or archive connection after
the repository files are present.

### GitHub Pages

After the owner deploys and verifies GitHub Pages, the project-site address is
expected to be:

`https://groksgalaxynet.github.io/Cronoscope/`

This address is **not claimed as live or verified by this document**. Use it
only after the repository owner confirms a successful deployment and public
browser check.

### Preview locally

Serve the static directory from the repository root:

```bash
python3.12 -m http.server 8012 --directory static_feasibility
```

Open the server address printed by Python, then stop it with `Ctrl+C` when you
are done. Do not open `index.html` directly with `file://`; browser security
rules prevent the packaged JSON catalog from loading in that mode.

The Pages workflow copies the contents of `static_feasibility/` into the
artifact root. Therefore a deployed project site starts at `/Cronoscope/`, not
`/Cronoscope/static_feasibility/`. For a Pages-style subpath test, serve the
assembled artifact beneath `/Cronoscope/`. The application uses relative asset
paths and has no live archive, Horizons, detector, or API dependency.

### What the static demonstration means

- Packaged SPHEREx imagery is a labelled display derived from public archive
  products. It is not a raw FITS viewer and PNG colors are not measurements.
- The coordinate form matches only retained five-decimal JPL Horizons endpoint
  coordinates. It does not perform a new coverage search or retrieve data.
- WCS-WAVE supplies local wavelength context at an image location. It is not a
  measured source spectrum.
- A two-epoch view, blink, a predicted position, or a registered difference can
  provide research context. None alone confirms a moving object, variability,
  source identity, or discovery.
- The gallery uses separately labelled illustrative Hubble images. Those images
  are not SPHEREx data.

## Full Python scientific application

The Python application is included for people who have appropriate, locally
available FITS products and understand the associated provenance and release
boundaries. Public-source checkout alone does not bundle the FITS products
needed for the real-data viewer or local replay examples.

The verified application environment is **Python 3.12** (Python 3.12.3 during
the maintained regression and documentation checks). Other Python versions are
not claimed as verified. Create a virtual environment and install the pinned
runtime dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-web.txt
```

For the browser/regression tools, install the additional development manifest
and Chromium:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
```

`requirements-research.txt` contains optional tools used by archival/research
workflows. It is not required to preview the static demonstration or install
the basic local web application.

With suitable local FITS products available, start the application from the
repository root:

```bash
python -m web_app.api
```

Follow the server address printed in the terminal. If the necessary FITS
products are absent, use the static demonstration rather than interpreting a
missing product as a scientific result.

## Scientific boundaries

- **WCS and WCS-WAVE:** celestial WCS maps pixels to sky coordinates. WCS-WAVE
  maps an image location to local wavelength context and bandwidth. Neither
  map alone produces a source spectrum.
- **Pixel readouts:** when a valid local FITS product is present, intensity,
  variance, flags, coordinates, time, release, detector, and local wavelength
  context can be inspected. Invalid pixels stay invalid; Cronoscope does not
  invent values.
- **Observation comparison:** comparisons require attention to registration,
  release, detector, calibration, uncertainty, image quality, and sky
  coverage. A difference image is research context, not a detection.
- **Moving-object exploration:** frozen Horizons positions are predictions at
  stated times. They can guide investigation but do not validate a detection.
  Current experimental candidates do not establish a validated blind
  moving-object discovery.
- **DR1:** the architecture has a documented compatibility assessment, but
  Cronoscope does not yet integrate DR1 spectral images or the 102-channel
  all-sky cube. The public release's DR1 compatibility note describes the
  planned separation of image and cube support.

## Troubleshooting

- **The static page is blank or targets do not load:** serve
  `static_feasibility/` with a web server rather than opening it with `file://`.
- **A Pages link returns 404:** the site may not yet be deployed, may still be
  propagating, or may require the repository owner to configure GitHub Pages.
  Do not treat the expected URL as a verified demonstration until the owner
  confirms it.
- **A Python import fails:** activate `.venv`, check the Python version, and
  reinstall from the pinned dependency manifests. Avoid unpinned upgrades.
- **The local viewer has no data:** the public release deliberately omits local
  FITS/replay products. Obtain appropriate public products with their
  provenance and release conditions before attempting full scientific use.
- **An archive request fails:** archive availability, coverage, and network
  responses are operational conditions, not evidence that a source is absent.

## Documentation, license, and attribution

- [README](README.md) — project overview and capabilities.
- [Static demonstration guide](static_feasibility/README.md) — static-app
  boundaries and local preview details.
- [Apache License 2.0](LICENSE) — original Cronoscope source and documentation
  only.
- [Third-party notices](THIRD_PARTY_NOTICES.md) — non-vendored dependency and
  asset notices.
- [Scientific data attribution](DATA_ATTRIBUTION.md) — SPHEREx, Horizons, and
  gallery provenance.
- [Creator letter](A_letter_from_creator.md) — creator's account of the
  project, preserved unchanged.

Cronoscope is independent and is not endorsed by NASA, JPL, Caltech, IRSA,
ESA, STScI, or Hubble.
