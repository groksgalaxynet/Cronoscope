# Cronoscope RELEASE-1 Publication Manifest

**Prepared:** 2026-11-14  
**Scientific-source checkpoint:** `5f0e5945cbf9c42b56ecf7923ef28c594f5c59ad`  
**Documentation successors:** `5ac99da` (`docs: rewrite public getting started guide`); `6eda872` (`docs: clarify Python and Pages entry point`)  
**Purpose:** clean public competition release only. This record supersedes the
2026-11-13 unresolved classification for the assets included here, based on the
primary sources listed below. It is not a NASA, JPL, Caltech, IRSA, ESA, or
STScI endorsement of Cronoscope.

## Include

| Material | Status | Conditions |
| --- | --- | --- |
| Original Python, HTML, CSS, JavaScript, workflow, documentation, and dependency manifests | INCLUDE | Apache-2.0 applies only to original Cronoscope work. Dependencies are not vendored. |
| `static_feasibility/` app, packaged JSON, and SPHEREx-derived PNG displays | INCLUDE | The listed products are public IRSA-hosted SPHEREx material/derivatives. Retain IRSA provenance, the SPHEREx acknowledgement, product/release labels, and no-endorsement wording. |
| Frozen JPL Horizons values in static content | INCLUDE | JPL SSD calls site data public domain; retain a NASA/JPL Solar System Dynamics citation, identify prediction context, and disclose transformations. |
| M31, M42, M87 gallery files | INCLUDE | Retain their visible credits. M87 remains subject to ESA/Hubble CC BY 4.0 attribution/link requirements. All gallery imagery stays labelled as illustrative and non-SPHEREx. |
| Cronoscope logo, mark, favicon, and animation used by the static app | INCLUDE | Owner-attested original AI-assisted branding. No AI service is asserted; comply with any applicable service terms and do not imply endorsement. |

## Exclude

| Material | Reason / effect |
| --- | --- |
| `.venv/`, caches, bytecode, logs, temporary files, credentials, local/private configuration | Environment or credential risk; not needed for the release. |
| `fits_files/`, `nasa_targets/`, `research_artifacts/`, `experimental/`, `experiments/`, `old/`, `vot_files/`, `csv/`, `txt/`, `py_files/`, broad research test corpus | Preserved in the private scientific repository. They are not needed for the self-contained static demonstration and would materially expand the public review surface. The full local FITS viewer needs separately acquired/approved local products. |
| `static_feasibility/SpectrophotometryTargets/`, related ZIP/XML exports, duplicate excluded branding paths | Not needed for the static demo and deliberately excluded from the Pages artifact. |
| Original `.git/` history and recovery reports | This export begins cleanly. It does not publish the development repository's history or recovery material. |

## Review before owner-approved publication

1. Verify the owner’s branding/AI-service provenance record remains complete.
2. Confirm every copied SPHEREx asset corresponds to public IRSA material and retain product-level provenance.
3. Confirm all visible gallery credits, including the M87 CC BY 4.0 credit/link, render in Pages.
4. Review the assembled Pages artifact and this inventory before the first push.

## Primary rights and attribution sources

- IRSA [Terms of Use of Data Hosted by IRSA](https://irsa.ipac.caltech.edu/data_use_terms.html): most public data served by IRSA have no usage restrictions.
- IRSA [SPHEREx mission page](https://irsa.ipac.caltech.edu/Missions/spherex.html): required SPHEREx publication acknowledgement.
- JPL SSD [FAQ](https://ssd.jpl.nasa.gov/faq.html): SSD data are public domain; retain source citation, modification clarity, fair use, and no-endorsement context.
- [NASA Hubble M31 record](https://science.nasa.gov/asset/hubble/hubble-m31-phatphast-mosaic/), [NASA Orion record](https://science.nasa.gov/asset/hubble/orion-nebula-3/), and [ESA/Hubble copyright](https://esahubble.org/copyright/).
