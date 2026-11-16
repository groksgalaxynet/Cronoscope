# CRONOSCOPE
### Exploring the Universe Across Wavelengths and Time

Cronoscope is an evidence-first astronomy exploration project prepared for the
2026 NASA Space Apps Challenge. It brings together genuine SPHEREx observations,
celestial coordinates, wavelength context, and observations made at different
times so that people can examine what the data can—and cannot—say.

Comparing observations across time can reveal changing context, predicted
motion, and candidates worth investigating. It does not by itself prove that a
source moved, changed brightness, or was newly discovered. Cronoscope is built
to keep that distinction visible.

Cronoscope is an independent project; it is not endorsed by NASA.

## Try Cronoscope

| Resource | Status |
| --- | --- |
| Public GitHub Pages demonstration | **Live static demonstration:** [groksgalaxynet.github.io/Cronoscope](https://groksgalaxynet.github.io/Cronoscope/) |
| Source repository | **Owner URL pending** — this checkout is the project source. |
| Getting started locally | [START HERE](START_HERE.md) |
| Project story | [A Letter From the Creator](A_letter_from_creator.md) |
| Static demonstration guide | [Static demonstration README](static_feasibility/README.md) |

## What Cronoscope can do

The project has two deliberately distinct experiences.

| Capability | Full Python scientific application | Static GitHub Pages demonstration |
| --- | --- | --- |
| SPHEREx data | Reads retained real Level-2 FITS observations | Shows bundled, labelled static PNG displays derived from retained cutouts |
| Coordinates | Handles celestial WCS and pixel-to-sky context | Matches only retained five-decimal frozen Horizons endpoint coordinates |
| Wavelength | Inspects WCS-WAVE wavelength mapping and local context | Shows labelled wavelength context; it is not a source spectrum |
| Pixel science | Provides pixel-level intensity, variance, flags, and coordinate readouts where available | Does not provide FITS pixel inspection or derive measurements from PNG colors |
| Time comparison | Supports bounded two-epoch visualization and registered comparison workflows | Provides packaged A/B views and blink; only validated bundled differences are shown |
| Data access | Uses retained local products and can support controlled live archive workflows | Makes no live IRSA, archive, Horizons, detector, or API request |
| Provenance | Preserves product, detector, release, and scientific context | Displays packaged provenance and explicit missing-data status |

The static site is a demonstration surface, not a browser version of the full
scientific application.

### DR1 progress — November 15, 2026

- **Production / verified application:** QR2 and QR3 scientific-image support,
  DR1 Wide (D1–D6) and DR1 Deep D1 spectral-image support, bounded DR1 cutout
  retrieval, visible collection provenance, and fail-closed cross-collection
  comparison guards.
- **Experimental research:** bounded HTTP Range access to a DR1 All-Sky Cube,
  persistent request/byte accounting, validated sampling of three genuine
  channels, and aligned IMAGE/NHITS/FLAGS extraction.
- **Not yet supported:** complete validation of all 102 cube channels,
  cube-based motion detection or temporal variability, uncertainty-aware cube
  photometry, source-spectrum claims from cube pixels, or unverified
  cross-product scientific comparisons.

### Experimental DR1 cube reader

An isolated research reader is available in
[`research/dr1_cube_reader/`](research/dr1_cube_reader/). It can inspect a
small, explicitly bounded region of a verified 102-channel SPHEREx DR1 All-Sky
Cube by using HTTP byte ranges and a durable request/byte ledger. It keeps
IMAGE, NHITS, and FLAGS aligned; rejects intentionally blank channels 51 and
52 unless explicitly acknowledged; limits regions to 32×32; and fails closed
on unsupported structure, data types, or product identity.

This is **not** a production viewer feature or a general archive browser. The
code does not download a complete cube, turn NHITS into uncertainty, decode
FLAGS semantics, or claim that cube pixels are source photometry, spectra,
epochs, variability, motion, or detections. See the
[reader contract](research/dr1_cube_reader/API_DESIGN.md),
[scientific limitations](research/dr1_cube_reader/SCIENTIFIC_LIMITATIONS.md),
and [DR1 compatibility note](DR1_COMPATIBILITY_NOTE.md).

### Experimental DR1 cube service and wavelength explorer

The isolated localhost package in
[`research/dr1_cube_service/`](research/dr1_cube_service/) adds a fixed
server-side product allowlist, persistent request/transfer budgets, a bounded
SHA-256-verified range cache, structured errors, and a minimal same-origin
wavelength explorer. In preserved-evidence mode the explorer supports channels
0, 20, and 100 and the two verified 4×4 regions without making an archive
request.

Start the service as documented in its
[README](research/dr1_cube_service/README.md), then open
`http://127.0.0.1:8766/experimental/dr1-cube`. This localhost research page is
separate from the production viewer and GitHub Pages. It displays genuine
IMAGE, NHITS, and raw FLAGS values with wavelength metadata and provenance;
it makes no source-photometry, source-spectrum, uncertainty, motion,
variability, or independent-calibration claim.

## Scientific foundations

**SPHEREx** is NASA's Spectro-Photometer for the History of the Universe, Epoch
of Reionization and Ices Explorer. Its products combine sky position, image
data, and spectral-coordinate information.

**FITS** is the astronomy data format used for the retained Level-2 products.
Cronoscope checks the scientific-image extensions and associated arrays rather
than treating a display image as the scientific data itself.

**Celestial WCS** maps image pixels to positions on the sky. **WCS-WAVE** maps
detector position to wavelength context. That wavelength context is not the
same thing as a measured source spectrum; a source spectrum requires its own
measurement, uncertainty, flags, and provenance.

**Time-domain comparison** can be useful, but only after considering image
registration, processing release, detector, data quality, flags, uncertainty,
and the fact that two frames may represent different sky locations. A
difference image is research context—not automatic evidence of a detection.

## Moving-object research

Cronoscope explores a careful chain of evidence:

1. Frozen JPL Horizons positions describe a **predicted** position at a stated
   observation time.
2. WCS and observation geometry determine whether that predicted position is
   meaningfully represented in a retained image.
3. Registered image differences can provide research context.
4. A candidate is not a detection until it has the required quality,
   calibration, positional, and statistical validation.

The current research results do **not** establish a validated blind
moving-object discovery. Predicted tracks, residual candidates, and visual
patterns are deliberately not presented as confirmed objects.

## Featured demonstrations

| Example | What is available | Scientific boundary |
| --- | --- | --- |
| 5122 Mucha (1989 AZ1) | Packaged two-epoch SPHEREx views, frozen predicted geometry, and a validated registered `B − A` research-difference display | The prediction and difference are not a confirmed detection. |
| Barnard's Star | Genuine packaged two-epoch SPHEREx D3 sky context | Invalid target-core pixels prevent a reliable motion measurement. |
| RW Aurigae | Genuine packaged two-epoch SPHEREx D3 sky context and separately labelled retained spectral measurements | The image pair does not establish variability; release/calibration and quality limitations remain. |
| R Draconis / WISE 0855 | Packaged two-epoch context | R Draconis has invalid central samples; WISE 0855 has low signal-to-noise. Neither is a detection claim. |
| Epsilon Indi B | Explicit imagery-pending state | No validated static cutout is substituted. |
| M31, M42, M87 gallery | Separately labelled bundled illustrative reference images | These are not SPHEREx data, photometry, or scientific measurement products. |

See the [target FITS inventory](NASA_TARGET_FITS_INVENTORY.md),
[scientific validation](NASA_TARGET_SCIENTIFIC_VALIDATION.md), and
[static-target integration notes](NASA_TARGET_STATIC_INTEGRATION.md) for the
retained evidence and limits.

## Architecture

1. **Data sources:** retained SPHEREx Level-2 products and documented NASA/IPAC
   IRSA provenance.
2. **Scientific processing:** Python modules in
   [`cronoscope_pipeline/`](cronoscope_pipeline/) handle controlled discovery,
   retrieval, FITS normalization, WCS/WCS-WAVE context, and comparison support.
3. **Local application:** [`web_app/`](web_app/) is a standard-library WSGI
   service that exposes the scientific viewer and retained local products.
4. **Browser visualization:** the local viewer presents image, coordinate,
   wavelength-context, provenance, and comparison information.
5. **Static packaging:** [`static_feasibility/`](static_feasibility/) contains
   the HTML/CSS/JavaScript Pages artifact and bundled demonstration assets.

## Installation and local use

### Full Python application

The verified baseline is Python 3.12 on Linux. The detailed environment guide
is [DEPENDENCY_SETUP.md](DEPENDENCY_SETUP.md).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-web.txt
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python -m web_app.api
```

Open <http://127.0.0.1:8000>. The local application needs its retained local
data products; live archive actions, where enabled, require a working archive
connection.

### Static demonstration

The static demo needs only a static-file server, not Python scientific
processing or a network connection after its bundled files are present:

```bash
./.venv/bin/python -m http.server 8012 --directory static_feasibility
```

Open <http://127.0.0.1:8012>. For Pages-style testing, serve it beneath a
project subpath such as `/cronoscope/`; relative asset paths are supported.

### Tests

```bash
.venv/bin/python -m pytest -q
```

The experimental reader's deterministic tests require the normal web/test
dependencies. Genuine response bodies, FITS products, SQLite ledgers,
checkpoints, and machine-local validation reports are deliberately excluded
from the public repository.

## Scientific integrity and limitations

- **Real versus illustrative imagery:** Static SPHEREx previews are labelled
  derived displays; gallery images are explicitly non-SPHEREx references.
- **Release boundaries:** QR2 and QR3 are not silently combined for a science
  conclusion. Processing and calibration differences matter.
- **Missing data:** A target with no validated cutout, such as Epsilon Indi B,
  is shown as unavailable rather than receiving a substitute image.
- **Difference images:** The static NASA-target pairs have no validated
  registered difference product and the browser does not synthesize one.
- **Research versus detection:** Visual context, predicted positions, blink,
  and residuals do not establish a confirmed moving object or variable source.
- **Static limits:** The Pages demo does not fetch an archive, perform arbitrary
  coordinate coverage searches, interpret PNG color as flux, or replace the
  full FITS/WCS viewer.

The private Barnard's Star DR1 research checkpoint and its discovery report are
intentionally excluded from this public release. They are isolated research
evidence, not a production integration. See the included
[DR1 compatibility note](DR1_COMPATIBILITY_NOTE.md) and
[pre-competition readiness audit](CRONOSCOPE_2026-11-13_PRECOMPETITION_READINESS_AUDIT.md)
for the public release boundary and readiness record.

## Verification

Local verification results recorded on November 13, 2026:

- **STATIC-1:** PASS
- **STATIC-2:** READY FOR OWNER-APPROVED DEPLOYMENT
- **Regression:** `207 passed, 16 subtests passed`
- **Frozen baseline preservation:** PASS
- **Local GitHub Pages-subpath browser acceptance:** PASS

The static demonstration was subsequently deployed and checked at
[groksgalaxynet.github.io/Cronoscope](https://groksgalaxynet.github.io/Cronoscope/).
The public site is the self-contained static demonstration; local verification
results remain the authority for the full FITS-driven Python application.

## Open source and attribution

Original Cronoscope source code and original project documentation are licensed
under the [Apache License 2.0](LICENSE). This license does not grant rights in
third-party software, NASA/IPAC data, scientific products, imagery, trademarks,
or logos.

Source-code licensing is separate from the terms, attribution, and access
conditions that apply to third-party software, NASA imagery, and scientific
data. Data provenance and attribution are documented in the
[third-party notices](THIRD_PARTY_NOTICES.md),
[scientific data attribution](DATA_ATTRIBUTION.md),
[publication asset manifest](PUBLICATION_ASSET_MANIFEST.md),
[NASA target FITS inventory](NASA_TARGET_FITS_INVENTORY.md),
[five-target feasibility assessment](NASA_FIVE_TARGET_FEASIBILITY.md), and
[spectral feasibility notes](CRONOSCOPE_SPECTRAL_FEASIBILITY.md).

## About the creator

Cronoscope is a solo-created project. Its origin, motivation, AI-assisted
development process, and long-term ambition are told in the creator's own
words in [A Letter From the Creator](A_letter_from_creator.md).

## NASA Space Apps Challenge 2026

Cronoscope is prepared for the 2026 NASA Space Apps Challenge. It makes no
claim of NASA endorsement, sponsorship, award, or competition result.

## Project status

- **Scientific implementation:** verified local FITS/WCS/WCS-WAVE and bounded
  comparison capabilities are available in the full Python application.
- **Static demonstration:** deployed at
  [groksgalaxynet.github.io/Cronoscope](https://groksgalaxynet.github.io/Cronoscope/).
- **Public deployment:** the interactive static demonstration is live; it does
  not include the local FITS products required by the full Python application.
- **Research features:** moving-object exploration and image-comparison results
  remain evidence-led research, not production detection claims.
- **DR1 Wide/Deep:** supported in the full local application with explicit
  release boundaries; QR2 and QR3 remain separately labelled and guarded.
- **DR1 All-Sky Cube:** a bounded experimental reader is published for research
  and reproducibility, but it is not integrated into the application or static
  demonstration.
- **Publication blocker:** required rights/redistribution review for packaged
  scientific, gallery, and branding assets remains unresolved; see the
  [publication asset manifest](PUBLICATION_ASSET_MANIFEST.md).
