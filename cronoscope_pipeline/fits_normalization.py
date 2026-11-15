"""Canonical SPHEREx FITS inventory, science-image selection, and WCS checks."""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from .models import (HduInventoryEntry, NormalizedFitsProduct, ObservationRecord,
                     RetrievalResult, WcsStatus)


def _has_celestial_wcs(header: fits.Header) -> bool:
    return bool(header.get("CTYPE1") and header.get("CTYPE2") and
                (str(header.get("CTYPE1")).upper().startswith(("RA", "GLON"))))


def _inventory(hdul: fits.HDUList) -> tuple[HduInventoryEntry, ...]:
    entries = []
    for index, hdu in enumerate(hdul):
        data = hdu.data
        shape = None if data is None else tuple(data.shape)
        entries.append(HduInventoryEntry(index, hdu.header.get("EXTNAME"), type(hdu).__name__, shape,
                                         hdu.header.get("BITPIX"), bool(data is not None and getattr(data, "ndim", 0) >= 2),
                                         _has_celestial_wcs(hdu.header)))
    return tuple(entries)


def _select_science_hdu(hdul: fits.HDUList) -> int | None:
    for index, hdu in enumerate(hdul):
        if str(hdu.header.get("EXTNAME", "")).upper() == "IMAGE" and getattr(hdu.data, "ndim", 0) == 2:
            return index
    for index, hdu in enumerate(hdul):
        if getattr(hdu.data, "ndim", 0) == 2 and _has_celestial_wcs(hdu.header):
            return index
    return None


def _validate_wcs(header: fits.Header, shape: tuple[int, int]) -> tuple[WcsStatus, WCS | None, tuple[tuple[float, float], ...] | None, str | None]:
    if not _has_celestial_wcs(header):
        return WcsStatus.MISSING, None, None, "No celestial CTYPE1/CTYPE2 pair"
    try:
        wcs = WCS(header).celestial
        if not wcs.has_celestial:
            return WcsStatus.INCOMPLETE, None, None, "Header advertises celestial axes but Astropy has no celestial WCS"
        height, width = shape
        x, y = (width - 1) / 2, (height - 1) / 2
        ra, dec = wcs.pixel_to_world_values(x, y)
        round_x, round_y = wcs.world_to_pixel_values(ra, dec)
        if not all(np.isfinite(value) for value in (ra, dec, round_x, round_y)):
            return WcsStatus.INVALID, None, None, "Non-finite pixel/sky transformation"
        if np.hypot(round_x - x, round_y - y) > 1e-4:
            return WcsStatus.INVALID, None, None, "Pixel/sky round-trip exceeds tolerance"
        corners = ((0, 0), (width - 1, 0), (width - 1, height - 1), (0, height - 1))
        footprint = tuple((float(a), float(b)) for a, b in zip(*wcs.pixel_to_world_values(*zip(*corners))))
        return WcsStatus.VALID, wcs, footprint, None
    except Exception as exc:
        return WcsStatus.INVALID, None, None, f"WCS validation failed: {exc}"


def _fits_timing(header: fits.Header) -> dict[str, object]:
    return {key: header[key] for key in ("DATE-OBS", "DATE-BEG", "DATE-AVG", "DATE-END", "MJD-OBS", "MJD-BEG", "MJD-AVG", "MJD-END", "TIMESYS") if key in header}


def _spectral_metadata(hdul: fits.HDUList, header: fits.Header) -> dict[str, object]:
    result = {key: header[key] for key in ("DETECTOR", "OBS_IN_SBAND", "FILTER", "BAND", "WAVELEN", "WAVE_MIN", "WAVE_MAX") if key in header}
    wave = next((hdu for hdu in hdul if str(hdu.header.get("EXTNAME", "")).upper() == "WCS-WAVE"), None)
    if wave is not None and getattr(wave.data, "names", None):
        result["WCS-WAVE_columns"] = list(wave.data.names)
        result["WCS-WAVE_rows"] = len(wave.data)
    return result


def normalize_fits_product(retrieval: RetrievalResult, observation: ObservationRecord | None = None) -> NormalizedFitsProduct:
    """Load a validated cached FITS product; image pixels stay out of JSON output."""
    if not retrieval.succeeded or not retrieval.cache_path:
        raise ValueError("normalize_fits_product requires a successful retrieval result")
    path = Path(retrieval.cache_path)
    with fits.open(path, memmap=False) as hdul:
        inventory = _inventory(hdul)
        selected = _select_science_hdu(hdul)
        warnings: list[str] = []
        if selected is None:
            return NormalizedFitsProduct(retrieval.cache_identity, str(path), None, None, None,
                                         archive_timing_mjd=None if observation is None else (observation.t_min_mjd, observation.t_max_mjd),
                                         archive_detector=None if observation is None else observation.band_label,
                                         archive_wavelength_m=None if observation is None else (observation.wavelength_min_m, observation.wavelength_max_m),
                                         hdu_inventory=inventory, warnings=("No 2-D IMAGE extension or 2-D celestial image was found.",),
                                         observation_id=None if observation is None else observation.observation_id)
        hdu = hdul[selected]
        image = np.asarray(hdu.data, dtype=float)
        named = {str(item.header.get("EXTNAME", "")).upper(): item for item in hdul}
        flags_hdu = named.get("FLAGS")
        variance_hdu = named.get("VARIANCE")
        quality_flags = None if flags_hdu is None else np.asarray(flags_hdu.data).copy()
        variance = None if variance_hdu is None else np.asarray(variance_hdu.data, dtype=float).copy()
        status, wcs, footprint, warning = _validate_wcs(hdu.header, image.shape)
        if warning:
            warnings.append(warning)
        fits_detector = None if hdu.header.get("DETECTOR") is None else str(hdu.header["DETECTOR"])
        if observation is not None and observation.collection in {"spherex_dr1", "spherex_dr1_deep"}:
            archive_match = re.fullmatch(r"SPHEREx-D([1-6])", observation.band_label or "", re.IGNORECASE)
            fits_match = re.fullmatch(r"D?([1-6])", fits_detector or "", re.IGNORECASE)
            if archive_match and fits_match and archive_match.group(1) != fits_match.group(1):
                raise ValueError(
                    f"DR1 detector identity mismatch: archive reports {observation.band_label}, "
                    f"but FITS DETECTOR is {fits_detector}."
                )
            if not archive_match or not fits_match:
                warnings.append("DR1 detector identity is incomplete; no detector value was invented.")
        return NormalizedFitsProduct(
            retrieval.cache_identity, str(path), selected, hdu.header.get("EXTNAME"), tuple(image.shape), image=image,
            image_unit=None if hdu.header.get("BUNIT") is None else str(hdu.header["BUNIT"]),
            finite_image_mask=np.isfinite(image), quality_flags=quality_flags, variance=variance,
            variance_unit=None if variance_hdu is None or variance_hdu.header.get("BUNIT") is None else str(variance_hdu.header["BUNIT"]),
            wcs=wcs,
            wcs_status=status, celestial_footprint_deg=footprint,
            archive_timing_mjd=None if observation is None else (observation.t_min_mjd, observation.t_max_mjd),
            fits_timing=_fits_timing(hdu.header), archive_detector=None if observation is None else observation.band_label,
            fits_detector=fits_detector,
            archive_wavelength_m=None if observation is None else (observation.wavelength_min_m, observation.wavelength_max_m),
            fits_spectral_metadata=_spectral_metadata(hdul, hdu.header), hdu_inventory=inventory, warnings=tuple(warnings),
            observation_id=None if observation is None else observation.observation_id,
            collection=None if observation is None else observation.collection,
            source_url=retrieval.source_url,
        )
