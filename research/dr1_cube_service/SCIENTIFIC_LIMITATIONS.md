# Scientific Limitations

- IMAGE contains coadded surface brightness, not extracted source photometry.
- Genuine supported IMAGE values retain the FITS unit `MJy/sr`.
- A pixel sampled across channels is not automatically a calibrated source
  spectrum.
- NHITS is observation contribution count, not uncertainty.
- The cube supplies no uncertainty array and the service invents none.
- FLAGS are raw integer bitmaps; no bit meaning is inferred.
- Channels 51 and 52 are intentionally blank and unavailable for ordinary
  sampling.
- Cube pixels are not Level-2 observations or observation epochs.
- The product cannot establish motion, variability, or a detection.
- The packaged public fixture exactly replays recorded verified result values;
  it does not perform a fresh raw-range decode. When private range evidence is
  explicitly supplied, agreement validates indexing, offset calculation,
  decoding, and alignment, not independent photometric calibration.
- DR1.6 validates three channels and two regions in one tile. It does not
  validate every channel, region, tile, or calibration state.
