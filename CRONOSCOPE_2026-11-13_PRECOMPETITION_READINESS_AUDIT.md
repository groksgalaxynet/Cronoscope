# CRONOSCOPE — FINAL PRE-COMPETITION READINESS AUDIT

**Date:** 2026-11-13  
**Mode:** read-only production audit. No production source, test, configuration, frozen baseline, FITS/VOTable, cache, or external archive state was changed. The sole new artifact is this requested report.

## Executive finding

Cronoscope is **READY WITH GAPS** for a defensible local demonstration of real, locally retained SPHEREx Level-2 image products, WCS/WAVE pixel context, and a two-epoch Barnard's Star image comparison. It is not ready to claim a moving-object discovery capability or an unqualified Barnard's Star spectrum. The most credible competition path is the local real-data viewer plus the explicitly labelled, registered two-epoch comparison; all display elements must keep their provenance and non-detection language visible.

## Audit method and scope

Inspected the repository, retained data and reports, current source, API/UI contract tests, frozen evidence references, Git state, and VOTable checksum. Ran the maintained suite once without modification:

```
source .venv/bin/activate && python -m pytest -q --disable-warnings
204 passed, 16 subtests passed in 89.59s (0:01:29)
```

No live IRSA, CDS, or JPL request was issued during this audit. Historical live results are identified as saved evidence, not a fresh service-status check.

## 1. Repository state and entry points

| Area | Current evidence | Classification |
|---|---|---|
| Primary application | `python -m web_app.api`, WSGI application in `web_app/api.py`, static browser UI in `web_app/static/` | VERIFIED |
| Main science path | `CronoscopeOrchestrator`: discovery, grouping, guarded retrieval, FITS normalization, footprint and frozen comparison | VERIFIED |
| Live archive path | IRSA SPHEREx SIA2/DataLink/FITS discovery/retrieval code in `cronoscope_pipeline/discovery.py` and `retrieval.py` | PARTIAL; not live-tested today |
| Standalone static explorer | `static_feasibility/` | STATIC DEMO; separate from launcher |
| Target resolution | bundled aliases plus optional CDS Sesame fallback in `web_app/target_resolver.py` | VERIFIED locally; live fallback not checked today |
| Local real-data viewer | retained FITS selection in `LOCAL_VIEWER_TARGETS` | VERIFIED |
| Moving-object explorer | frozen Phase-40B/40D metadata/evidence exposed by `web_app/moving_objects.py` | VERIFIED as an evidence viewer, EXPERIMENTAL scientifically |

### Integrity

The Git worktree is not clean: tracked pipeline/UI/test files are modified, two historical paths are deleted, and many reports/data/support files are untracked. This audit did not attribute or alter those changes. Therefore repository integrity is **PARTIAL**, despite the current regression passing. Before submission, the owner should identify the intended release contents and preserve a commit/archive; this is a release-control issue, not evidence that the current application is broken.

## 2. Regression baseline

Current discovery produced exactly the historical requested result: **204 passed, 0 failed, 0 skipped/xfailed reported, 16 subtests passed, 89.59 s**. There were no failing tests.

The count is higher than older 156/160/202/203 reports because the maintained `tests/` suite has expanded with later browser, local-science-viewer, moving-object-explorer, QR3/release-policy, target-gallery, and release-candidate contracts. `pytest.ini` limits discovery to `tests/`, keeping archival executable research scripts out of the maintained run.

This validates local/frozen behavior. It does not prove current availability of IRSA, CDS, JPL Horizons, or a new archive download.

## 3. Science-pipeline readiness

| Capability | Status | Evidence and boundary |
|---|---|---|
| SPHEREx archive access | PARTIAL | Live SIA2 discovery and retrieval code exists; saved Phase 5 acceptance recorded M31 QR2/QR3 metadata discovery. No fresh external query in this audit. |
| QR2 | VERIFIED for local/current code | Default collection; real retained QR2 FITS and guarded comparison supported. |
| QR3 | PARTIAL | Explicit selectable collection, saved QR3 fixture and retained M31 QR3 FITS; same-release live pair retrieval was deliberately not acceptance-tested. |
| Cross-release protection | VERIFIED | Release-policy tests ensure QR2↔QR3 is `CROSS_RELEASE_COMPARISON_BLOCKED` before retrieval, including forged IDs. |
| FITS ingestion | VERIFIED | Normalization and API tests read real L2 IMAGE/VARIANCE/FLAGS/WCS-WAVE products; local pixel values are checked against FITS arrays. |
| Celestial WCS | VERIFIED for retained products | Tests assert valid WCS for R Draconis, Barnard's Star, RW Aur; viewer returns RA/Dec pixel readouts. |
| WCS-WAVE | VERIFIED for retained products | Native-pixel wavelength/bandwidth lookup, map/overlay and invalid/unsupported states are implemented. It is calibration context, not a source spectrum. |
| Multi-band/wavelength | PARTIAL | Native local wavelength context and compatible-pair metadata are available. No general multi-image source spectral extraction exists. |
| Forced-photometry importer | VERIFIED | `spectral_measurements.py` preserves wavelength, flux, uncertainty, flags, fit quality, MJD, detector and release from official VOTables. |
| Science warnings | VERIFIED | WAVE is labelled non-flux context; source-spectrum-unavailable state is explicit; residual candidate and moving-object UI preserve “not a detection”; reviewed Barnard renderer supports CAUTION/flags/fit-quality behavior. |

### Spectrophotometry and Barnard’s Star job

The saved recovery metadata and original file establish the following without a new request:

* UWS job `GjHQoPAY8RsdzCXNyByqK3` is **COMPLETED** (2026-11-09 17:22:54 UTC).
* The original IRSA measurement-table VOTable exists at `experimental/barnards_star_spectrophotometry_20261109/barnards_star_irsa_uws_GjHQoPAY8RsdzCXNyByqK3_measurements.vot`; its SHA-256 currently matches the saved recovery value: `db36bacb7889da2ec2d65d5dece5e7bcf041f967f17516ab54e93c5ad49774ba`.
* It contains six finite QR2 forced-photometry measurements, 2.3063452–5.0012207 um, with flux/uncertainty in uJy. Coordinates match the saved Gaia-propagated submission coordinate and MJD is within the requested interval.
* The importer was run and recorded `AVAILABLE`.
* All six measurements are **CAUTION**, not USABLE: each carries the documented bad-pixel warning, and some have nonfunctional/dichroic/overflow warnings or high `fit_ql`; undocumented set bits are retained rather than invented.

Thus the VOTable is genuine, downloaded, importable, and traceable. A Barnard UI presentation is only scientifically usable as six **unconnected, caution-annotated forced-photometry points** with flags, fit quality, limits, and provenance visible. It is not a continuous spectrum, clean spectrum, or standalone source-identification proof. The currently selectable primary spectra are R Draconis (536 rows) and RW Aurigae (165 rows); neither may be relabelled as Barnard's Star.

## 4. Barnard’s Star showcase audit

| Dimension | Current state | Data class |
|---|---|---|
| Astrometry | Gaia DR3 source 4472832130942575872 propagated with Astropy to the retained observation epoch; saved coordinate 269.4463514844°, +4.7671323567° | DERIVED FROM REAL Gaia data |
| Imaging | local QR2 L2 D3 FITS at MJD 60902.865381 and second retained D3 FITS at MJD 61165.083638 | REAL SPHEREx data |
| SPHEREx context | IMAGE/VARIANCE/FLAGS, WCS and WCS-WAVE served through local viewer | REAL SPHEREx data |
| Spectrophotometry | six original IRSA QR2 forced-photometry measurements; reviewed CAUTION | REAL data, restricted interpretation |
| Epoch/time | two local real products available for A/B, blink, registered difference and temporal relationship | REAL observation metadata; comparison output is DERIVED |
| Proper motion | observation-epoch propagation evidence exists; no Barnard-specific live animation/track UI established | DERIVED evidence / UI MISSING |
| Visualization | target switch, image, zoom/pan/click, pixel RA/Dec/value/variance/flags/WAVE context, and local comparison are browser-tested | WORKING NOW |
| Provenance | filenames, release/detector/MJD, IRSA identifiers in VOTable/recovery, Gaia propagation evidence are retained | VERIFIED, but must be surfaced in demo narration/UI |

The application’s Local Real Data viewer deliberately reports “Source spectrum unavailable” for its image targets, including Barnard's Star. This protects against representing WCS-WAVE context as measured flux. The genuine-spectrum panel does not currently make Barnard selectable, so the VOTable cannot accidentally appear there as an unqualified measurement.

## 5. Moving-object and time-domain readiness

| Function | Status | What it actually means |
|---|---|---|
| Multiple observation/epoch grouping | VERIFIED | Metadata is grouped chronologically; local replay and selected real targets exercise A/B. |
| Registration/difference/blink | VERIFIED | Frozen/local comparison renders registered B, zero-centred difference, blink and central display crops. |
| Barnard image comparison | VERIFIED | Two retained D3 epochs run through the same contract; no motion detection claim follows. |
| Proper-motion coordinate propagation | PARTIAL | Used and documented for Barnard spectrophotometry request; not a general interactive proper-motion product. |
| Observation timeline/temporal navigation | VERIFIED for existing UI contract | Present in later tests/UI; it is navigation, not scientific inference. |
| Moving-object explorer | VERIFIED as static/frozen evidence viewer | Lists 19 frozen tracks, predicted old/new Horizons positions and archived observation metadata. |
| JPL Horizons integration | EXPERIMENTAL/SAVED | Frozen prior Horizons responses/provenance are used; no fresh ephemeris call is made by the viewer/audit. |
| Candidate logic | EXPERIMENTAL | Frozen residual evidence is labelled “Experimental image evidence — not a detection.” |
| General moving-object detection | NOT IMPLEMENTED as a defensible capability | Blind validation history is zero successful winners over five pairs; do not present candidates as discoveries. |

## 6. Viewer/frontend readiness

The following labels reflect browser/API tests in the current 204-pass run, not just source presence.

| Judge interaction | Status | Notes |
|---|---|---|
| Application starts / health | WORKING NOW | WSGI and Chromium tests start isolated local servers. |
| Target selection/naming | WORKING NOW | Local aliases include M31/M87/M42; manual coordinates remain independent. |
| Barnard's Star | WORKING NOW for local real FITS and two-epoch comparison | No selectable, unqualified spectrum. |
| M31, M87, M42 | STATIC DEMO ONLY for gallery imagery | Bundled NASA Science images are explicitly labelled not SPHEREx; resolver is working, but no locally retained real FITS viewer target exists for them. |
| RW Aurigae | WORKING NOW | Local real FITS viewer plus genuine official spectrum panel. |
| Zoom / pan | WORKING NOW | Tested in gallery and local science viewer. |
| Display field-of-view | WORKING NOW | Full/central 50%/central 25% crops after registration; no new retrieval/resampling/detection. |
| Coordinate/pixel readout | WORKING NOW | RA/Dec, intensity, variance, flags, MJD/release/detector/WAVE context. |
| Click/select candidate/object | WORKING NOW for residual candidates and pixel probes | Candidate selection is evidence inspection, not confirmation. |
| Wavelength controls/overlay | WORKING NOW | Native WCS-WAVE map/overlay only; explicitly not flux density. |
| Provenance display | PARTIAL | API retains substantial provenance and spectra render provenance; the demo needs deliberate visible narration/panel verification for each showcased artifact. |
| Spectra display | WORKING NOW for R Draconis and RW Aurigae only | Both are genuine official exports. Barnard UI integration is missing. |
| Time/epoch controls | WORKING NOW | Replay/local A/B, blink and timeline contracts. |
| Moving-object explorer | WORKING NOW as frozen experimental viewer | Not a live detection pipeline. |
| Loading and error states | WORKING NOW | Explicit network/request errors, invalid target/coordinate/release, missing static-image fallback, unknown image/comparison, invalid pixels, and unsupported overlap statuses are tested. |
| Live archive search/retrieval | BACKEND READY / EXTERNAL DEPENDENCY | Code and prior acceptance evidence exist; current availability and coverage were not tested. |

One historical numeric-step finding was subsequently covered by browser tests using exact resolver coordinates and a 0.005° radius. The current suite passes it, but a manual launch should still be performed before judges arrive because tests run an isolated browser/server rather than the final competition laptop workflow.

## 7. Provenance audit

| Artifact or display | Origin | Audit finding |
|---|---|---|
| Local R Draconis, Barnard's Star, RW Aur and WISE 0855 FITS | NASA/IPAC IRSA SPHEREx L2, retained locally | Real FITS; viewer checks native arrays and metadata. |
| Local viewer PNGs/overlays/readouts | Local derived renderings of those FITS | Safe only when labelled image/pixel/WCS-WAVE context. |
| Barnard six-point VOTable | IRSA SPHEREx Spectrophotometry Tool, saved original export | Genuine; CAUTION restrictions mandatory. |
| R Draconis/RW Aur spectra | IRSA Spectrophotometry Tool exports | Genuine, target-specific; no transfer to other targets. |
| Barnard propagated position | Gaia DR3 data + local Astropy derivation | Derived real-data product; saved methodology/evidence. |
| Moving-object old/new coordinates | saved JPL Horizons predictions + frozen SPHEREx/IRSA inventory | Real-source, frozen evidence; presentation must say frozen/experimental. |
| Residual candidates / comparison products | local derived output from selected inputs and frozen detector | Experimental candidate evidence, never detection. |
| M31/M87/M42 gallery images | bundled NASA Science/Hubble imagery | Static illustrative images, explicitly not SPHEREx. |
| `static_feasibility/demo/*` | static demo, fixtures, and selected derived assets | Not the production launcher; never describe it as a live archive or detection result. |
| Archived test fixtures (`fits_files`, `tests/`, CSV/TXT) | frozen/synthetic/test evidence as named | Valid regression evidence, not automatically current sky measurements. |

No major displayed artifact examined was of unknown origin. The material risk is **presentation confusion**, especially static target-gallery images and WCS-WAVE displays; preserve the existing labels and add a spoken provenance transition in the demo.

## 8. Shortest defensible judge demo path

**Feasible today (offline, local):**

1. Launch `python -m web_app.api`; open the local app.
2. Open **Local real-data viewer** and select **Barnard's Star**.
3. State that the image is a retained SPHEREx QR2 L2 D3 product; show filename, MJD, detector/release and WCS metadata.
4. Zoom/pan and click a valid pixel. Show actual MJy/sr, variance, flags, RA/Dec and WCS-WAVE context. State clearly that this is not source flux.
5. Enable wavelength-context overlay; vary wavelength/tolerance. State that it maps native local calibration context only.
6. Invoke **Compare target** to load the two real local Barnard epochs; assign A/B and compare.
7. Show Image A/B, blink and zero-centred registered difference. Say “candidate/residual comparison, not moving-object detection.”
8. Open diagnostics/provenance fields and distinguish input observations from derived comparison output.

**Breaks / do not include unless completed separately:**

* Do not use M31/M87/M42 gallery pictures as SPHEREx imagery.
* Do not show the Barnard VOTable as a clean/continuous spectrum; it is not integrated into the selection UI and requires its CAUTION display.
* Do not claim a Barnard proper-motion visualization, source extraction, spectral cube, live archive response, or moving-object discovery.
* Do not make live IRSA the centerpiece: external availability/coverage and potentially significant retrieval remain dependencies.

An optional, separate genuine-spectra segment can show R Draconis or RW Aurigae with its named, official forced-photometry data, but it should not interrupt the Barnard narrative or imply equivalence.

## 9. Competition risks and priorities

### P0 — must have for tomorrow (3)

1. **Release and rehearse the offline Barnard path.**  Confirm the final worktree content, one-command launch, local assets, and the exact seven-step demo above on the competition machine. This is the primary credibility/control risk.
2. **Make provenance and scientific boundary legible in the live demo.** Confirm existing labels appear: real SPHEREx FITS, WCS-WAVE is not flux, residuals/candidates are not detections, gallery images are not SPHEREx. A judge must never have to infer this.
3. **Decide and lock the Barnard spectrum stance.** Safest P0 choice: omit it. If shown, integrate only the preserved six discrete CAUTION points with raw flags, fit quality, error bars, UWS/IRSA provenance and no interpolated line; otherwise do not present it.

### P1 — high value

* Add/verify a compact in-app Barnard provenance/limitations card linked to its two FITS products and the recovered VOTable review, if it can be done without destabilizing the local demo.
* Run one small, read-only live archive smoke test only if network is reliable; record service failure as unavailable rather than a null scientific result.
* Curate a judge-friendly single target flow and ensure external/gallery material cannot visually dominate genuine SPHEREx panels.

### P2 — nice to have

* Improve target-wide provenance navigation and M31/M87/M42 real-data acquisition/presentation after a legitimate live-data path is selected.
* Extend proper-motion visualization from saved astrometry into an explicit, clearly derived overlay.

### P3 — post-competition/research

* General moving-object detection or performance claims.
* New detector generations, threshold tuning, broad population studies, fresh mass downloads, architectural rewrite, or spectral extraction from Level-2 images.
* Cross-release comparison. The guard should remain intact.

## 10. Tomorrow’s execution plan

### First 2 hours

| Objective | Why / component to reuse | Expected output and acceptance test | Risk |
|---|---|---|---|
| Freeze an intentional competition release and run the local Barnard demo end-to-end | Reuse `web_app.api`, local viewer, retained `nasa_targets/` products | Launch on target machine; perform the eight-step path without network; `python -m pytest -q --disable-warnings` remains 204 + 16 | LOW |
| Verify visible scientific labels in the rendered browser, not source only | Reuse existing `science_viewer.js`, `app.js`, spectral renderer messages | Screenshot/checklist confirms real-FITS provenance, WAVE-not-flux, candidate-not-detection, gallery-not-SPHEREx | LOW |
| Choose spectrum policy | Reuse Phase 5.6 VOTable review | Written decision: omit Barnard spectrum, or defined CAUTION-only scope with acceptance checklist | LOW |

### Next 4 hours

| Objective | Why / component to reuse | Expected output and acceptance test | Risk |
|---|---|---|---|
| Polish a single provenance-forward judge script | Reuse local target viewer and existing diagnostic fields | 2–3 minute spoken/runbook path; a reviewer can identify every source and derived step | LOW |
| If spectrum was approved, make the smallest safe integration | Reuse VOTable importer and reviewed renderer | Six unconnected points only; all are CAUTION; errors, flags, `fit_ql`, units, UWS/IRSA provenance, and no-continuum warning visible; focused/full tests pass | MEDIUM |
| Optional live smoke test | Reuse `/api/search`, bounded coordinates/radius | A documented success or an explicit archive-unavailable message; do not make it required to demo | MEDIUM |

### Remainder of day 1

| Objective | Why / component to reuse | Expected output and acceptance test | Risk |
|---|---|---|---|
| Practice recovery from normal failures | Reuse explicit invalid input/loading/error UI and Local Replay fallback | Offline launch/restart and malformed input produce clear states; no judge-facing dead end | LOW |
| Prepare a provenance cheat sheet | Reuse this audit, filenames, VOTable recovery JSON | One-page demo notes separating real, derived, static, and experimental material | LOW |
| Improve only presentation blockers found in rehearsal | Preserve frozen pipeline and release guard | Small, tested UI changes only; no detector/science rewrite | MEDIUM |

### Day 2 before submission

| Objective | Why / component to reuse | Expected output and acceptance test | Risk |
|---|---|---|---|
| Final clean-room rehearsal and capture | Reuse offline Barnard demo | Start from fresh process; full test pass; record a short backup video/screenshots if allowed | LOW |
| Final release/provenance review | Reuse regression and audit | No static image is called SPHEREx; no residual is called a detection; all claims match saved evidence | LOW |
| Stop scope creep | Reuse working local path | No late archive bulk download, algorithm change, QR2/QR3 bypass, or architecture rewrite | LOW |

## 11. Final readiness scorecard

```
CRONOSCOPE PRE-COMPETITION READINESS
=====================================

Repository integrity:       PARTIAL
Regression suite:           PASS
SPHEREx archive pipeline:   PARTIAL
Real SPHEREx data:          PASS
WCS/WAVE handling:          PASS
Spectrophotometry:          PARTIAL
Barnard's Star showcase:    PARTIAL
Time-domain capability:     PARTIAL
Moving-object capability:   PARTIAL
Frontend/viewer:            PARTIAL
Data provenance:            PASS
Judge demo path:            PARTIAL

OVERALL STATUS:
READY WITH GAPS
```

The strongest working capability is the offline local-real SPHEREx FITS viewer and carefully bounded two-epoch comparison. The central blocker is not an application crash: it is ensuring that the competition demo does not overstate WCS-WAVE, residual evidence, static imagery, or the caution-flagged Barnard VOTable as a clean spectrum or detection.
