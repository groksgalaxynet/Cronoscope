# Third-Party Notices

## Scope

The root [LICENSE](LICENSE) is Apache License 2.0 for original Cronoscope
source code and original project documentation only. It does not grant rights
in third-party software, scientific data, imagery, trademarks, or logos.

Cronoscope does not vendor Python packages, JavaScript libraries, fonts, or
icons. The GitHub Pages artifact is plain project HTML, CSS, JavaScript, and
packaged data/image assets. Python dependencies are installed separately by a
user from the pinned manifests; their own distributions carry their licenses
and notices.

## Declared Python dependencies

These direct dependencies are declared in `requirements-*.txt`; they are not
copied into the source repository or the Pages artifact. Versions below are the
declared pins. License identifiers are upstream project licenses and must be
rechecked if any package is ever bundled or redistributed.

| Package | Version | Upstream license | Notice / redistribution status |
| --- | ---: | --- | --- |
| Astropy | 8.0.1 | BSD-3-Clause | Separately installed; not bundled. |
| NumPy | 2.5.3 | BSD-3-Clause | Separately installed; not bundled. |
| Pillow | 12.3.0 | HPND | Separately installed; not bundled. |
| reproject | 0.21.0 | BSD-3-Clause | Separately installed; not bundled. |
| Requests | 2.34.2 | Apache-2.0 | Separately installed; not bundled. |
| SciPy | 1.18.1 | BSD-3-Clause | Separately installed; not bundled. Binary wheels can carry additional component notices. |
| pytest | 9.2.0 | MIT | Development-only; not bundled. |
| Playwright | 1.64.1 | Apache-2.0 | Development-only; browser runtime is separately downloaded; not bundled. |
| ImageIO | 2.37.4 | BSD-2-Clause | Research-only; not bundled. |
| Matplotlib | 3.11.2 | PSF-style license | Research-only; not bundled. |
| PIMS | 0.7 | BSD-3-Clause | Research-only; not bundled. |
| PyVO | 1.9.1 | BSD-3-Clause | Research-only; not bundled. |
| dask-image | 2026.5.0 | BSD-3-Clause | Research-only; not bundled. |

Evidence: the pinned manifests and the installed package metadata were inspected
on 2026-11-13. Authoritative license text remains with each upstream package
distribution; this table is a navigation aid, not a replacement for those
notices.

## Deployment components

The Pages workflow references `actions/checkout`, `actions/configure-pages`,
`actions/upload-pages-artifact`, and `actions/deploy-pages`. These execute in
GitHub Actions and are not copied into Cronoscope's source tree or Pages
artifact. GitHub's action repositories and service terms govern them.

## Packaged assets and outstanding review

The file-level release decision record is
[PUBLICATION_ASSET_MANIFEST.md](PUBLICATION_ASSET_MANIFEST.md). It distinguishes
original project work from source-publication and Pages-artifact blockers.

| Asset class | Repository / Pages status | Notice or provenance | Publication status |
| --- | --- | --- | --- |
| SPHEREx-derived PNG previews and JSON payloads | Source repository and Pages artifact | See [DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md) and the publication manifest | **UNRESOLVED / P0: redistribution terms must be confirmed before public release.** |
| Hubble gallery images: `m31-hubble.jpg`, `m42-hubble.png`, `m87-hubble.jpg` | Source repository and Pages artifact | Exact NASA/ESA release records and conditions are in [PUBLICATION_ASSET_MANIFEST.md](PUBLICATION_ASSET_MANIFEST.md) | **CLEARED WITH ATTRIBUTION: retain each full visible credit; M87 is ESA/Hubble CC BY 4.0.** |
| Cronoscope logo PNG, mark PNG, logo MP4, and favicon | Source repository and Pages artifact | Owner declaration: original Cronoscope branding created with AI assistance; favicon is an older resized logo created for the static webpage before animated-logo integration; tool/service unspecified | **OWNER-ATTESTED: observe any applicable AI-service terms and third-party-component rights.** |
| Spectrophotometry XML / ZIP exports | Source repository; excluded from Pages artifact | IRSA identifiers retained in the exports | **P0: confirm archive redistribution terms before public source release.** |
| Retained FITS, test FITS, research checkpoint FITS, and research screenshots | Source repository; excluded from Pages artifact | Existing scientific provenance remains in repository reports | **P0: confirm redistribution terms or exclude from public source release.** |

No claim is made here that a credit line alone grants a redistribution license.
