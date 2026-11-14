# Cronoscope spectral feasibility

## Decision

Use **RW Aurigae** for one precomputed, single-processing-release prototype spectrum. Its two packaged target pixels are finite and the existing local diagnostics are high-S/N (formal values 202 and 278), unlike R Draconis (invalid core) and WISE 0855 (formal S/N 1.18/1.93). Barnard's Star also has invalid target-core pixels and very high proper motion; asteroids require time-dependent ephemerides. RW Aur's variability remains a limitation: display measurements by `mjd`, do not combine epochs into one variability or spectral-feature claim.

## Official path: SPHEREx Spectrophotometry Tool

The public [SPHEREx Data Explorer](https://irsa.ipac.caltech.edu/applications/spherex/) includes the public [Spectrophotometry Tool documentation](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html). It accepts a specified sky position (or a target list), performs Tractor forced photometry across the Quick Release 2/3 Spectral Images that cover it, and returns a low-resolution spectrum. The returned table includes `wavelength` (µm), `flux` and `flux_err` (µJy), `lambda_width`, `flags`, `fit_ql`, `flux_bkg`, `lvf_id`, `det_id`, `mjd`, and `data_collection`.

- **Access:** publicly accessible browser tool. No mandatory authentication is documented; logging in is recommended because jobs/results can be transient.
- **Programmatic access:** IRSA documents programmatic SIA2 and cutout access for spectral-image MEFs, but does **not** document a public API for submitting a spectrophotometry extraction job. Treat the extractor as an interactive UWS job, then download its result; do not rely on an undocumented browser endpoint.
- **Output:** the normal download is a VOTable/XML (`.vot` despite the `.xml`-style name). [IRSA Viewer](https://irsa.ipac.caltech.edu/applications/irsaviewer/) can convert it to CSV, IPAC table, or FITS. Thus a static GitHub Pages graph can consume a checked-in, precomputed CSV or compact JSON derived from the original VOTable.
- **Existing QR2 inputs:** yes. The tool retrieves its own QR2/QR3 IMAGE, FLAGS, VARIANCE, PSF, and solid-angle inputs; do not attempt to treat one Level-2 image cutout as a full spectrum.
- **Epochs:** the output supplies `mjd`, `lvf_id`, and `data_collection`; split or filter rows into labelled epoch windows client-side only after preserving those provenance fields. The service does not make a scientific two-epoch comparison automatically.
- **Practical limits:** at most 20 sources per run. A typical source may cover about 200 images and take roughly 10 minutes after queueing; packaging may take another 3–5 minutes. Job Monitor results are intended to persist about 14 days, and the service may be interrupted during maintenance or heavy load.

## Minimum genuine prototype dataset

Run one **point-source** extraction for RW Aur at its catalog coordinate, scoped to one release (`qr2`) and a defined observation-time window. Retain the source VOTable plus a small browser payload containing, at minimum:

`wavelength_um`, `flux_ujy`, `flux_err_ujy`, `lambda_width_um`, `flags`, `fit_ql`, `mjd`, `det_id`, `lvf_id`, and `data_collection`.

The first interface should plot flux density with error bars; flag/fit-quality gaps should be visible rather than interpolated. A date filter can expose one epoch at a time. A two-epoch overlay is appropriate only if both subsets are quality-screened and held to the same processing release. The UI must identify this as **forced-photometry measurements**, not an illustrative curve or a confirmed variability measurement.

## Data products and verified access

| Need | Official source | Use |
| --- | --- | --- |
| Extracted source spectrum | [Spectrophotometry Tool](https://irsa.ipac.caltech.edu/applications/spherex/) and [output documentation](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html) | Preferred genuine flux/uncertainty spectrum; VOTable export. |
| Level-2 spectral images | [SIA2 endpoint](https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr2) and [data-access guide](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/) | Discovery and spatial cutouts only; each image is a single position-dependent LVF wavelength sample. |
| Spatial cutouts | [IRSA Cutout Service](https://irsa.ipac.caltech.edu/ibe/cutouts.html) | Context/inspection, not a 102-channel source spectrum. |
| Wavelength mapping and response | [Spectral WCS / product guide](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-products/) and [spectral calibrations](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/spherex_spectral_calibrations.html) | Needed only for an eventual independent extractor; science analysis uses CWAVE/CBAND, not visualization WCS-WAVE alone. |

SPHEREx obtains a spectrum by placing a source at multiple detector positions across exposures; wavelength is position-dependent. Level-2 MEFs provide `IMAGE`, `FLAGS`, and `VARIANCE`, while calibration files provide response and wavelength mapping. They are inputs to extraction, not a substitute for its flux table.

## Post-hackathon architecture

**GitHub Pages:** serve versioned, precomputed CSV/JSON spectrum payloads and an in-browser chart; retain original VOTables, flags, uncertainties, MJD, product/release IDs, and a link to the IRSA extraction record. Do not issue extraction jobs from the browser.

**External service:** discover products via [SIA2](https://irsa.ipac.caltech.edu/SIA?COLLECTION=spherex_qr2), request only needed cutouts for review, submit/manual-manage official spectrophotometry runs, validate and cache their VOTables, then publish immutable browser payloads. Rate-limit, queue, cache by target/coordinate/release/time window, and expose IRSA failures rather than fabricating a spectrum.

**Next action:** manually submit one QR2, point-source RW Aur extraction in the public tool; download the VOTable promptly, screen flags and `fit_ql`, then package one labelled epoch as static CSV/JSON. Do not download spectral images or build the viewer until that result is reviewed.
