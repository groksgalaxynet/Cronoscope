# Scientific Limitations

- Cube IMAGE values are coadded surface brightness, not source photometry.
- A spatial pixel across channels is not automatically a calibrated source spectrum.
- NHITS records contributing coverage and is not an uncertainty estimate.
- No variance array exists and none is invented.
- FLAGS remain raw integer bitmaps unless official semantics are separately validated.
- Channels 51 and 52 are intentionally blank and are never interpolated.
- The cube combines observations over time and cannot establish variability or motion.
- Saved-evidence replay validates software reproducibility for one genuine sample only.
- Synthetic fixtures validate code behavior, never SPHEREx measurements.
- Production integration and additional live retrieval require separate authorization.
