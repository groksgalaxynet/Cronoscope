# Scientific Data and Image Attribution

> **RELEASE-1 status update (2026-11-14):** The earlier P0/P1 review below is
> preserved as historical context. The clean public competition export applies
> the verified [IRSA public-data terms](https://irsa.ipac.caltech.edu/data_use_terms.html)
> and [JPL SSD reuse guidance](https://ssd.jpl.nasa.gov/faq.html). See
> [RELEASE1_PUBLICATION_MANIFEST.md](RELEASE1_PUBLICATION_MANIFEST.md) for the
> current include/exclude/review decision and continuing attribution conditions.

## Scope and status

This document records provenance and publication review status; it is not a
license grant. The root [LICENSE](LICENSE) applies only to original Cronoscope
source code and documentation, not to scientific data or imagery.

Primary references reviewed on 2026-11-13: [NASA image/media use guidance](https://www.nasa.gov/nasa-brand-center/images-and-media/),
[IRSA SPHEREx mission and acknowledgement page](https://irsa.ipac.caltech.edu/Missions/spherex.html),
[JPL Horizons documentation](https://ssd.jpl.nasa.gov/horizons/manual.html),
[STScI content-use policy](https://www.stsci.edu/copyright), and the gallery
source records linked below.

## SPHEREx / NASA-IPAC IRSA products

Cronoscope's retained FITS products, derived static previews, and packaged
observation metadata are associated with NASA SPHEREx Quick Release products
accessed through NASA/IPAC IRSA. Product identifiers, detector/band details,
dates, checksums, and validation results are retained in:

- [NASA target FITS inventory](NASA_TARGET_FITS_INVENTORY.md)
- [NASA target scientific validation](NASA_TARGET_SCIENTIFIC_VALIDATION.md)
- [NASA five-target feasibility assessment](NASA_FIVE_TARGET_FEASIBILITY.md)
- [Static target integration](NASA_TARGET_STATIC_INTEGRATION.md)

The official [SPHEREx QR overview](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html)
identifies DOI `10.26131/IRSA652` for QR2 (and `10.26131/IRSA662` for QR3) and
specifies the SPHEREx mission acknowledgement. Its focused review establishes
access, citation, and acknowledgement; it does **not** state redistribution
terms for original FITS, derived PNG visualizations, derived JSON values, or
spectrophotometry exports. The retained data must not be represented as NASA
endorsement of Cronoscope.

**Publication status:** **UNRESOLVED / P0.** IRSA's mission page requires a
specific SPHEREx acknowledgement for published material, but the official
pages reviewed in this audit do not establish a redistribution permission for
these retained FITS files or derived assets. Confirm the applicable IRSA/NASA
terms in writing before public source or Pages publication.

## JPL Horizons-derived predictions

Frozen target positions and geometry are documented as JPL Horizons predictions
in the static catalog and research manifests. They are prediction context, not
measured detections. Raw Horizons responses are retained in research/test
materials, while the Pages artifact contains only derived frozen values.

**Publication status:** **UNRESOLVED / P1.** The reviewed JPL Horizons
documentation establishes the service and its ephemeris purpose, but this audit
did not locate an explicit redistribution grant for raw responses or derived
packaged values. Confirm required citation and reuse terms before public-source
release.

## Hubble illustrative gallery

The Pages artifact includes three explicitly non-SPHEREx gallery images:

| File | Retained credit |
| --- | --- |
| `assets/target-gallery/m31-hubble.jpg` | NASA, ESA, Benjamin Williams (UWashington), Zhuo Chen (UWashington), L. Clifton Johnson (Northwestern); image processing: Joseph DePasquale (STScI) |
| `assets/target-gallery/m87-hubble.jpg` | NASA, ESA and the Hubble Heritage Team (STScI/AURA) |
| `assets/target-gallery/m42-hubble.png` | NASA, ESA, Hubble Space Telescope Orion Treasury Project Team; Hubble ACS and ESO MPI 2.2 m La Silla WFI mosaic |

Credits are displayed by the gallery. The official source records are:

- M31: [NASA Hubble M31 PHAT+PHAST Mosaic](https://science.nasa.gov/asset/hubble/hubble-m31-phatphast-mosaic/), 2025-01-16.
- M42: [NASA Orion Nebula asset](https://science.nasa.gov/asset/hubble/orion-nebula-3/), 2006-01-11.
- M87: [ESA/Hubble HEIC0815f](https://esahubble.org/images/heic0815f/),
  2008-08-05; [ESA/Hubble CC BY 4.0 terms](https://esahubble.org/copyright/).

The M31/M42 NASA records identify the matching display derivatives and full
credits. The M87 file matches the ESA/Hubble record's exact dimensions and
visual content. STScI's policy still cautions that materials from other
institutions may carry separate rights.

**Publication status:** **CLEARED WITH ATTRIBUTION.** Retain each full source
credit in a visible, associated presentation; preserve the ESA/Hubble link and
CC BY 4.0 conditions for M87; do not imply NASA, ESA, STScI, or Hubble
endorsement. This clearance applies only to these three verified gallery files,
not to SPHEREx products or other repository assets.

## NASA name, identifiers, and endorsement

NASA media guidance permits factual use subject to its guidelines but restricts
NASA identifiers and any implication of sponsorship or endorsement. Cronoscope
uses mission names descriptively and states that it is not NASA-endorsed. No
NASA insignia, logotype, or seal is intentionally packaged as a Cronoscope
asset.

## Publication surfaces

The Pages workflow copies `THIRD_PARTY_NOTICES.md`, `DATA_ATTRIBUTION.md`,
`PUBLICATION_ASSET_MANIFEST.md`, and `LICENSE` into the curated artifact. It
excludes `SpectrophotometryTargets/` and unused duplicate artwork. That
exclusion does not resolve the rights review for the assets it does publish.
