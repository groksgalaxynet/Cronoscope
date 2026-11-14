# Publication Asset Manifest

> **RELEASE-1 status update (2026-11-14):** This 2026-11-13 audit is preserved
> as historical evidence. For the clean public competition export, see
> [RELEASE1_PUBLICATION_MANIFEST.md](RELEASE1_PUBLICATION_MANIFEST.md), which
> records the subsequently verified IRSA public-data terms and JPL SSD
> public-domain/citation guidance. It controls the release decision for the
> files included in this export.

**Audit date:** 2026-11-13

**Scope:** tracked source files and the GitHub Pages artifact assembled by
`.github/workflows/deploy-static-pages.yml`. This is a provenance and release
review record, not a grant of rights.

## Decision rule

`CLEARED` means the project owns the original work and applies the root
Apache-2.0 license. `CLEARED WITH ATTRIBUTION` means the upstream source and
required acknowledgement are retained and the applicable reuse terms have been
verified. `OWNER-ATTESTED` means the project owner has declared original
creation, with any applicable AI-service terms and third-party components still
to be observed. `OWNER CONFIRMATION REQUIRED` means an owner must attest to the
project's rights. `UNRESOLVED` means the available evidence does not establish
redistribution rights. `RESTRICTED` means the item must not be included in a
public release without a new authorization.

An acknowledgement is not treated as a redistribution license. NASA's media
guidance also prohibits implied endorsement, and IRSA's SPHEREx mission page
requires an acknowledgement for published use of SPHEREx products. See
[DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md) for the authoritative source links
and wording.

## Essential application source

| Files | Surface | Classification | Basis / required action |
| --- | --- | --- | --- |
| Original project Python, HTML, CSS, JS, test, and documentation files, excluding the asset groups below | Source repository and, where copied, Pages | **CLEARED** | Original Cronoscope work; covered by [LICENSE](LICENSE). Review any future third-party contribution before treating it as original work. |
| `requirements-*.txt`, `.github/workflows/deploy-static-pages.yml` | Source repository | **CLEARED WITH ATTRIBUTION** | Manifests and workflow configuration are original; the packages and GitHub Actions are not vendored. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). |

## GitHub Pages artifact inventory

The workflow copies all of `static_feasibility/` except
`SpectrophotometryTargets/`, `cronoscope logo.PNG`, and `cronoscope-mark.png`,
then copies this manifest, `LICENSE`, `THIRD_PARTY_NOTICES.md`, and
`DATA_ATTRIBUTION.md`. Therefore each row marked unresolved below is a public
deployment blocker even though the static experience is technically offline.

| Exact file set | Classification | Provenance / release condition |
| --- | --- | --- |
| `static_feasibility/index.html`, `app.js`, `styles.css`, `spectral-data.js`, `spectral-renderer.js`, `static-coordinate-selector.js`, `static-featured.js`, `static-guide.js`, `static-panel-controls.js`, `static-provenance.js`, `static-science-viewer.js`, `static-target-gallery.js`, `README.md` | **CLEARED** | Original presentation code/documentation. Gallery credit strings do not clear the images themselves. |
| `static_feasibility/demo/catalog.json`; `321899.json`; `5122.json`; `nasa-targets.json`; `spectra/index.json`; `spectra/r-draconis.json`; `spectra/rw-aur.json` | **UNRESOLVED** | Frozen astronomy metadata and derived values. Retained provenance identifies IRSA/Horizons context, but no reviewed redistribution grant for this public packaging was found. |
| `static_feasibility/demo/321899-a.png`, `321899-b.png`, `321899-difference.png`, `321899-wavelength-a.png`, `321899-wavelength-b.png`, `5122-difference.png`, `5122-field-a.png`, `5122-field-b.png`, `5122-target-a.png`, `5122-target-b.png` | **UNRESOLVED** | Derived scientific previews/difference displays; must be cleared with the underlying product rights holder or removed from the release candidate. |
| `static_feasibility/demo/nasa-barnard-a.png`, `nasa-barnard-b.png`, `nasa-r-draconis-a.png`, `nasa-r-draconis-b.png`, `nasa-rw-aur-a.png`, `nasa-rw-aur-b.png`, `nasa-wise-0855-a.png`, `nasa-wise-0855-b.png` | **UNRESOLVED** | Derived from retained SPHEREx/IRSA products. The IRSA site provides an acknowledgement, not a documented redistribution authorization located in this audit. |
| `static_feasibility/demo/track-17529-a.png`, `track-17529-b.png`, `track-175348-a.png`, `track-175348-b.png`, `track-177020-a.png`, `track-177020-b.png`, `track-19651-a.png`, `track-19651-b.png`, `track-215451-a.png`, `track-215451-b.png`, `track-321899-a.png`, `track-321899-b.png`, `track-3487-a.png`, `track-3487-b.png`, `track-4748-a.png`, `track-4748-b.png`, `track-8686-a.png`, `track-8686-b.png`, `track-9013-a.png`, `track-9013-b.png`, `track-9055-a.png`, `track-9055-b.png` | **UNRESOLVED** | Derived visualization assets associated with retained SPHEREx observations and frozen Horizons context. Verify the rights for both underlying data and any retained raw inputs. |
| `static_feasibility/assets/target-gallery/m31-hubble.jpg` (`047c11044e94a80d3dfe0a28c53ecf04f781efae910526f070485616bd0d0143`) | **CLEARED WITH ATTRIBUTION** | Exact official source: [NASA Hubble M31 PHAT+PHAST Mosaic](https://science.nasa.gov/asset/hubble/hubble-m31-phatphast-mosaic/), released 2025-01-16. The local 2000×467 display file corresponds to NASA's listed 1997×467 display derivative; retain the complete NASA/ESA/Williams/Chen/Johnson/DePasquale credit and no-endorsement context. |
| `static_feasibility/assets/target-gallery/m42-hubble.png` (`8cfc2e4eb5558a3c177fa448ff3d275e02524e22cf3e5ac50c46b862b4257906`) | **CLEARED WITH ATTRIBUTION** | Exact official source: [NASA Orion Nebula asset](https://science.nasa.gov/asset/hubble/orion-nebula-3/), released 2006-01-11. NASA lists a 2000×960 PNG—the local file's exact dimensions—and the full NASA/ESA/Orion Treasury/Robberto credit. Retain that credit and no-endorsement context. |
| `static_feasibility/assets/target-gallery/m87-hubble.jpg` (`7bdba97ffecff6434e32787573c1d02084692f2646b2efa690e0fa98351122c4`) | **CLEARED WITH ATTRIBUTION** | Exact official source: [ESA/Hubble HEIC0815f](https://esahubble.org/images/heic0815f/), released 2008-08-05, exact 3854×3815 dimensions and matching visual content. ESA/Hubble places its images under [CC BY 4.0](https://esahubble.org/copyright/): retain the full credit, link when online, and do not imply ESA/Hubble endorsement. |
| `static_feasibility/assets/cronoscope-logo.png` (`f41373596b07c2758b32116051e8b31f61b135ef2adf3cd21c21a94460991ad1`), duplicate `static_feasibility/cronoscope logo.PNG`, `static_feasibility/cronoscope-mark.png` (`5ba8231f9282a6aad5bef8a7339ed22b6a1dfdb40e8d88ce2b2ff20494d9e206`), and `static_feasibility/assets/cronologo.mp4` (`907155bbf66dd80040773bc516d68af544c551547b8890d37b86ace45de3c750`) | **OWNER-ATTESTED** | On 2026-11-13, the project owner declared all Cronoscope branding original work created with AI assistance. The six-second MP4 depicts the blue telescope looking around. No AI service/tool is named or inferred; observe applicable service terms and third-party-component rights. |
| `static_feasibility/favicon.png` (`b1483f5fa9203fc566f8c3777d365ade11cb018755d881057e5850996bc61ec1`) | **OWNER-ATTESTED** | On 2026-11-13, the owner declared it an older resized version of the original Cronoscope logo, created for the static webpage before the animated logo was integrated. The prior hash/metadata observation does not override this owner provenance declaration; no AI service/tool is named or inferred. |

## Repository-only scientific and research assets

| Exact tracked set | Pages status | Classification | Required action |
| --- | --- | --- | --- |
| `fits_files/*.fits` (17 tracked files) | Excluded by source layout, not a Pages input | **UNRESOLVED** | Preserve provenance; establish archive redistribution terms before making this repository public. |
| `nasa_targets/original_0.03deg/*.fits` (5), `nasa_targets/context_0.10deg/*.fits` (1), `nasa_targets/analysis_evidence.json` | Not Pages inputs | **UNRESOLVED** | Same IRSA/SPHEREx issue; JSON is derived from retained products. |
| `research_artifacts/dr1_2026_11_13/barnard_dr1_cutout.fits` and its manifests | Not Pages inputs | **UNRESOLVED** | Checkpoint integrity is verified, but preservation is not public redistribution clearance. |
| `static_feasibility/SpectrophotometryTargets/248.167611_66.754979/248.167611_66.754979.xml`, `76.9564535_30.4013327/76.9564535_30.4013327.xml`, `SpectrophotometryTargets2ips/SpectrophotometryTargets.zip`, `SpectrophotometryTargets2.zip`, and `README` | Explicitly excluded from Pages | **UNRESOLVED** | Archive export terms and source request provenance need review before source-publication. |
| `static_feasibility/cronoscope logo.PNG` (same hash as packaged logo) and `static_feasibility/cronoscope-mark.png` (`5ba8231f9282a6aad5bef8a7339ed22b6a1dfdb40e8d88ce2b2ff20494d9e206`) | Explicitly excluded from Pages | **OWNER-ATTESTED** | See the owner declaration above. Exclusion prevents Pages distribution but does not affect the applicable ownership/service-term record. |

## DOCUMENTATION-4 publication decision

| Asset group | Status | Evidence | Remaining action |
| --- | --- | --- | --- |
| M31, M42, M87 gallery files | **CLEARED WITH ATTRIBUTION** | Exact NASA/ESA official records; M87 has explicit ESA/Hubble CC BY 4.0 terms. | Preserve visible full credits and no-endorsement wording. |
| Logo, mark, and logo video | **OWNER-ATTESTED** | Owner's 2026-11-13 declaration of original AI-assisted creation. | Retain a record of any applicable AI-service terms; no service is named here. |
| Favicon | **OWNER-ATTESTED** | Owner declaration: older resized original Cronoscope logo created for the static webpage before animated-logo integration. | Retain a record of any applicable AI-service terms; no service is named here. |
| SPHEREx FITS, PNG derivatives, JSON derivatives, spectrophotometry exports | **UNRESOLVED** | IRSA QR overview supplies access, DOI, and acknowledgement, not redistribution terms found in this focused review. | Obtain applicable public-redistribution terms. |
| Horizons values / raw responses | **UNRESOLVED** | Prior documented source review located no redistribution grant. | Obtain reuse/citation direction before public-source release. |

## Evidence and history finding

The science-derived demonstration assets and other unresolved items remain in
pre-existing repository history (the gallery and branding paths were
introduced in commit `0075cff`, although the three gallery files are now
verified). Removing a file only from a current working tree or a new commit
would not remove it from an already-public Git history. A rights-cleared public
release therefore requires either (1) clearance for every unresolved item, or
(2) a curated new repository/export containing only cleared material. History
rewriting or asset removal was **not** performed by this documentation audit.

## Minimum owner decisions before public launch

1. Obtain terms that specifically allow redistribution of the retained SPHEREx
   FITS and derivative static assets, then add the required acknowledgement/DOI.
2. Record the applicable AI-service terms, if any, for the owner-attested
   branding and video; no tool or service is asserted by this manifest.
3. Decide between clearing all historical source assets or publishing a new,
   clean curated repository/export. Do not deploy Pages while its unresolved
   assets remain in the assembled artifact.
