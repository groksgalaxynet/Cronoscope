# NASA target scientific validation

## Method and containment

The supplied target coordinates were propagated to each observation date using the listed proper motions, then transformed through the local FITS celestial WCS. All eight propagated positions are **inside** their respective 18 × 18 pixel science footprints, 8.5–8.9 pixels from the nearest edge. This is an exact image-WCS containment result, not an inference from the cutout centre.

The target positions (zero-based image pixels) are: R Draconis (8.06, 8.33) and (8.18, 8.10); Barnard's Star (8.05, 8.40) and (8.60, 8.56); RW Aur (8.97, 8.41) and (8.62, 8.28); WISE 0855 (8.26, 8.84) and (8.60, 8.40). The coordinate propagation is deliberately a linear proper-motion check: it does not model parallax, radial velocity, or a full astrometric solution.

`IMAGE`, `VARIANCE`, `FLAGS`, `ZODI`, and `PSF` were inventoried separately. Non-finite image pixels are retained as invalid samples. `FLAGS` were not silently turned into a blanket rejection mask: a nonzero flag word has product-specific bit semantics and must be decoded before it can establish a science-quality decision. In particular, the ubiquitous D3 nonzero bit pattern does **not** mean every D3 pixel is invalid.

## Per-target findings

| Target | Target-pixel condition | Scientific result | Assessment |
| --- | --- | --- | --- |
| R Draconis | Nearest predicted target pixel is non-finite in both epochs (24 and 17 non-finite image pixels respectively). | No defensible brightness or variability measurement from this pair. | Needs more data / a larger or differently placed cutout. |
| Barnard's Star | Nearest predicted target pixel is non-finite in both epochs (four non-finite pixels per image). | The expected proper-motion displacement cannot be measured from the target core. | Context only; do not present as a motion detection. |
| RW Aur | Predicted target pixels are finite in both epochs. A simple 2-pixel aperture diagnostic gives high formal S/N (202 and 278), but is not calibrated aperture photometry. | The diagnostic declined by about 9.5% between the two products; this is **not** a validated variability claim because it spans `v20`/`v24`, has no PSF/aperture correction or flag-bit screening, and all aperture samples include nonzero flag words. | Context only; promising follow-up, not a static scientific result. |
| WISE 0855 | Predicted target pixels are finite. | Simple local diagnostics have formal S/N 1.18 and 1.93, below a defensible detection threshold. | Unsuitable for a detection/variability story with these two cutouts. |

The checked preview overlays are in [`nasa_targets/analysis_previews`](nasa_targets/analysis_previews). They show the WCS-propagated target position over real imagery; they are evidence aids, not flux-calibrated visual products.

## Scientific conclusion

All eight products are real, readable, target-containing SPHEREx L2B cutouts. That establishes data provenance and positioning, but it does not establish a publishable detection, proper motion, or variable-source measurement for every target. No result here relies on a bright pixel as a detection surrogate or on unqualified raw image brightness.
