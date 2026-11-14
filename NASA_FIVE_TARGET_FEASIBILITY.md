# NASA five-target SPHEREx feasibility

Investigation date: 2026-10-29. This is discovery and download preparation only. No new FITS files were saved, no frozen algorithm was changed, and an SIA2 result is **not** treated as proof of target containment.

## Method and guardrails

- Initial regression: **160 passed** (`python -m pytest -q --disable-warnings`).
- Live metadata came from the existing `cronoscope_pipeline.discovery.discover_observations` path, with `CALIB=2`, a 0.03-degree search circle, and each QR collection queried separately.
- Catalog coordinates are ICRS/J2000. High-proper-motion positions were propagated with Astropy linear space motion to each product MJD. The calculation intentionally omits parallax and radial velocity where a consistent six-parameter solution was not available; it is a discovery coordinate, not a replacement for fitted astrometry.
- Candidate products were screened against their live `s_region` polygons in a local tangent-plane check. Final FITS WCS containment, flags, variance, IMAGE selection, and registration remain required after owner-approved cutout download.
- A streamed request was used only to verify each recommended **0.03-degree cutout URL** returns `200 application/fits`; bodies were not retained. Full FITS downloads were not performed. `HEAD` is unsupported by this cutout endpoint (405), so it is not used as a false negative.

## Catalog coordinates and target interpretation

| Target | Catalog designation / interpretation | ICRS/J2000 coordinate | Proper motion used | Demonstration premise |
| --- | --- | --- | --- | --- |
| Barnard’s Star | GJ 699 / NAME Barnard’s star; M4V BY Dra variable | 269.452077°, +4.693365° | μRA*=−801.551, μDec=+10362.394 mas/yr | Very high proper motion; 7.4 arcsec predicted across the proposed QR2 D3 pair. |
| Epsilon Indi B | ε Indi B is the wide brown-dwarf companion; **Ba and Bb are its close T-dwarf pair**, not two separate wide-field targets | 331.0656°, −56.7901° (published B/Ba location) | combined-pair literature value approximately (+3976, −2500) mas/yr | Potential motion target, but not recommended yet: the first product-level cutout test returned `422 Arrays do not overlap`. SPHEREx should be treated as unresolved for the Ba/Bb pair unless WCS/pixel evidence shows otherwise. |
| WISE 0855−0714 | WISEA J085510.74−071442.5; Y2 brown dwarf | 133.818908°, −7.247048° | μRA*=−8123.7, μDec=+673.2 mas/yr | Strongest motion baseline (~8.15 arcsec/year); D6 matches its known strong ~4.5 μm emission, but detectability is unvalidated. |
| RW Aur | V* RW Aur; classical T Tauri system | 76.956526°, +30.401438° | μRA*=+7.23, μDec=−20.33 mas/yr | Brightness-variability candidate, not a motion target; compare the same detector only. |
| R Draconis | V* R Dra; Mira variable | 248.167611°, +66.754979° | not applied in this screen | Strongest variability candidate because of deep-field cadence. The 245.6-day catalog period is context, not a phase prediction. |

Catalog sources: [SIMBAD Barnard’s Star](https://simbad.cds.unistra.fr/simbad/sim-id?Ident=Barnard%27s+Star), [SIMBAD WISE 0855](https://simbad.cds.unistra.fr/simbad/sim-id?Ident=WISEA+J085510.74-071442.5), [SIMBAD RW Aur](https://simbad.cds.unistra.fr/simbad/sim-id?Ident=RW+Aur), [SIMBAD R Dra](https://simbad.cds.unistra.fr/simbad/sim-id?Ident=V%2A+R+Dra), and the ε Indi Ba/Bb astrometric discussion in [Kasper et al.](https://doi.org/10.1051/0004-6361/200912981). The WISE 0855 mid-infrared rationale is supported by [NASA NTRS](https://ntrs.nasa.gov/citations/20160011255).

## Live archive inventory

Counts are raw returned Level-2 FITS product rows / native observation IDs / distinct start times. The words “wide” and “deep” identify the collection; do not combine QR2 and QR3 in a scientific comparison without a specific calibration review.

| Target | QR2 wide | QR2 deep | QR3 wide | QR3 deep | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| Barnard’s Star | 252 / 128 / 129 | 0 / 0 / 0 | 124 / 62 / 62 | 0 / 0 / 0 | Wide-survey coverage; QR2 baseline 2025-08-15 to 2026-05-05 for screened D3 candidates. |
| Epsilon Indi B | 341 / 185 / 185 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | Archive coverage is abundant, but the first proposed B/Ba coordinate/product cutout did not overlap. |
| WISE 0855 | 257 / 130 / 130 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | QR2 coverage reaches 2025-05-05 to 2026-05-11 in screened D6 candidates. |
| RW Aur | 225 / 114 / 115 | 0 / 0 / 0 | 112 / 57 / 57 | 0 / 0 / 0 | Both wide releases have coverage; use QR2 pair only initially. |
| R Dra | 553 / 279 / 280 | 1243 / 630 / 631 | 0 / 0 / 0 | 706 / 355 / 357 | By far the richest cadence; QR2 deep is the initial same-release comparison pool. |

All collections supplied native D1–D6 coverage when nonzero, except QR3-deep R Dra’s returned rows were D1/D4. Archive D3 is 1.6301–2.4346 μm and D6 is 4.4115–5.0096 μm. These are detector ranges, not proof that two arbitrary fields sample an identical narrow spectral slice; the IMAGE WCS-WAVE extension must be inspected after download. IRSA notes that all six bands are not simultaneously on the same target position, which is why this manifest avoids cross-detector comparison. See the [IRSA SPHEREx overview](https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/overview.html).

## Candidate assessment and selection

| Target | Status | Best next pair | Why / remaining uncertainty |
| --- | --- | --- | --- |
| R Dra | **P1 strongest** | QR2-deep D3, 2025-04-24 → 2026-05-06 | 377-day same-detector baseline and dense deep coverage make a brightness-variation demonstration plausible. Need IMAGE+FLAGS+VARIANCE and fixed-aperture/registration validation; no variability has been measured here. |
| Barnard’s Star | **P1 strong** | QR2-wide D3, 2025-08-15 → 2026-05-05 | Propagated position moves ~7.4 arcsec. Both compact cutout endpoints returned FITS. Need WCS pixel coordinates and PSF-aware centroiding before calling it visible motion. |
| RW Aur | **P2** | QR2-wide D3, 2025-09-11 → 2026-03-02 | Same-detector, 172-day brightness comparison; motion is negligible. FITS cutout endpoints work, but variability must be separated from detector/PSF/background effects. |
| WISE 0855 | **P3 / high scientific reward, high risk** | QR2-wide D6, 2025-05-05 → 2026-05-11 | ~8.15-arcsec predicted shift and both cutout endpoints work. It is extremely faint outside the mid-IR; a source detection and usable S/N are not established. |
| Epsilon Indi B | **HOLD** | none selected | 62 D3 archive-footprint candidates were found by metadata, but the first proposed direct cutout at the propagated coordinate returned `422 Arrays do not overlap`. Resolve the correct astrometric reference (Ba, Bb, photocentre, and orbit) and validate with FITS WCS before selecting any download. |

The recommended immediate order is R Dra pair, Barnard pair, RW Aur pair, then WISE 0855 pair. That is eight compact cutouts rather than eight 61–72 MB full detector files. Full-file metadata implies about **560 MiB** for those eight files; cutout response lengths were not supplied by IRSA, so their total is **unknown** until the owner downloads them. Epsilon Indi B is deliberately excluded from the initial manifest.

## Existing local data and small-scale validation

Existing `fits_files/` contains 16 valid QR2 science files (`atlas_aug_d3.fits`, `epoch_dec_d3.fits`, `test6_*`, and `test7_case*`) plus one invalid 130-byte fixture. They are unrelated fields, not any of these five targets, so none can substantiate a target demonstration. Existing evidence confirms the pipeline’s normal IMAGE/FLAGS/VARIANCE/ZODI/PSF/WCS-WAVE inventory behavior, but it does not validate the five new target candidates.

Required after owner approval, per downloaded cutout: validate FITS and `EXTNAME=IMAGE`; inspect FLAGS and VARIANCE; run exact FITS WCS containment at the propagated time; compare WCS-WAVE at the target pixel; use same-detector pairs; estimate registration; and retain a null result if the source is absent or ambiguous. The current QR2 PSF-header correction notice should also be checked against each file’s `VERSION` header before photometric claims: [IRSA notice](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/psfhdrerr.html).

## Provenance and limitations

This preparation uses QR2 product metadata. Cite the dataset as **SPHEREx Team (2025), SPHEREx Quick Release Spectral Images – QR2, DOI [10.26131/IRSA652](https://doi.org/10.26131/IRSA652)**. The required acknowledgment is: “This publication makes use of data products from the Spectro-Photometer for the History of the Universe, Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration.”

No detection, light curve, astrometric measurement, or successful registration is claimed in this document. QR2 and QR3 were inventoried separately and must not be mixed for a science result without calibration compatibility work. The static website cannot obtain these products live because the prior browser experiment found IRSA discovery and FITS Fetch blocked by CORS.
