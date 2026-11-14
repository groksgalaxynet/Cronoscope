"""Read-only access to the Level-2 alternate spectral WCS (WCS key ``W``)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from .models import NormalizedFitsProduct


_SIP_PREFIXES = ("A_", "B_", "AP_", "BP_")
_SIP_ORDERS = {"A_ORDER", "B_ORDER", "AP_ORDER", "BP_ORDER"}


class SpectralMappingStatus(str, Enum):
    VALID = "VALID"
    UNAVAILABLE = "UNAVAILABLE"
    MALFORMED = "MALFORMED"
    OUTSIDE_SUPPORTED_DOMAIN = "OUTSIDE_SUPPORTED_DOMAIN"
    UNKNOWN_UNITS = "UNKNOWN_UNITS"


@dataclass(frozen=True)
class SpectralMapping:
    status: SpectralMappingStatus
    detector: str | None
    image_shape: tuple[int, ...] | None
    table_shape: tuple[int, ...] | None = None
    x_shape: tuple[int, ...] | None = None
    y_shape: tuple[int, ...] | None = None
    values_shape: tuple[int, ...] | None = None
    wavelength_unit: str | None = None
    bandwidth_unit: str | None = None
    wavelength_range_um: tuple[float, float] | None = None
    bandwidth_range_um: tuple[float, float] | None = None
    archive_range_m: tuple[float | None, float | None] | None = None
    warning: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self) | {"status": self.status.value}


@dataclass(frozen=True)
class SpectralPixelResult:
    status: SpectralMappingStatus
    x: float
    y: float
    wavelength_um: float | None = None
    bandwidth_um: float | None = None
    warning: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self) | {"status": self.status.value}


def _open(product: NormalizedFitsProduct):
    return fits.open(Path(product.cache_path), memmap=True)


def _spectral_header_without_sip(header: fits.Header) -> fits.Header:
    """Copy a header for alternate WAVE-TAB construction without celestial SIP.

    SPHEREx publishes SIP terms for the primary astrometric WCS and WAVE-TAB
    under alternate key ``W`` in the same IMAGE header.  Astropy otherwise
    attaches the primary SIP model to the alternate WCS, despite WAVE-TAB not
    declaring ``-SIP``.  IRSA's SPHEREx tutorial specifies that SIP must be
    disabled for the spectral WCS because detector/filter wavelength is
    independent of telescope optical distortion.  This operates on a copy;
    the source FITS header is never changed.
    """
    clean = header.copy()
    for keyword in list(clean):
        if keyword in _SIP_ORDERS or keyword.startswith(_SIP_PREFIXES):
            del clean[keyword]
    return clean


def spectral_wcs(hdul: fits.HDUList) -> WCS:
    """Create the SPHEREx alternate WAVE-TAB WCS with no celestial SIP model."""
    return WCS(_spectral_header_without_sip(hdul["IMAGE"].header), fobj=hdul, key="W")


def inspect_spectral_mapping(product: NormalizedFitsProduct) -> SpectralMapping:
    """Inspect the FITS WCS-WAVE table without changing product or detector state."""
    try:
        with _open(product) as hdul:
            if "WCS-WAVE" not in hdul:
                return SpectralMapping(SpectralMappingStatus.UNAVAILABLE, product.archive_detector, product.image_shape,
                                       warning="No WCS-WAVE extension.")
            image, table = hdul["IMAGE"], hdul["WCS-WAVE"]
            required = {"X", "Y", "VALUES"}
            if not required.issubset(table.columns.names or []):
                return SpectralMapping(SpectralMappingStatus.MALFORMED, product.archive_detector, product.image_shape,
                                       warning="WCS-WAVE lacks X, Y, or VALUES.")
            values = np.asarray(table.data["VALUES"])
            x, y = np.asarray(table.data["X"]), np.asarray(table.data["Y"])
            unit1, unit2 = image.header.get("CUNIT1W"), image.header.get("CUNIT2W")
            if str(unit1).lower() not in {"um", "micron", "microns"} or str(unit2).lower() not in {"um", "micron", "microns"}:
                return SpectralMapping(SpectralMappingStatus.UNKNOWN_UNITS, product.archive_detector, product.image_shape,
                                       tuple(table.data.shape), tuple(x.shape), tuple(y.shape), tuple(values.shape), str(unit1), str(unit2),
                                       warning="Alternate WCS units are not established as microns.")
            if values.ndim < 4 or values.shape[-1] != 2 or not np.all(np.isfinite(values)):
                return SpectralMapping(SpectralMappingStatus.MALFORMED, product.archive_detector, product.image_shape,
                                       tuple(table.data.shape), tuple(x.shape), tuple(y.shape), tuple(values.shape), str(unit1), str(unit2),
                                       warning="VALUES is not a finite tabular wavelength/bandwidth pair field.")
            wave, width = values[..., 0], values[..., 1]
            return SpectralMapping(SpectralMappingStatus.VALID, product.archive_detector, product.image_shape,
                                   tuple(table.data.shape), tuple(x.shape), tuple(y.shape), tuple(values.shape), str(unit1), str(unit2),
                                   (float(np.min(wave)), float(np.max(wave))), (float(np.min(width)), float(np.max(width))),
                                   product.archive_wavelength_m)
    except (OSError, KeyError) as exc:
        return SpectralMapping(SpectralMappingStatus.UNAVAILABLE, product.archive_detector, product.image_shape, warning=str(exc))


def wavelength_at_pixel(product: NormalizedFitsProduct, x: float, y: float) -> SpectralPixelResult:
    """Evaluate FITS alternate WCS ``W`` at a zero-based IMAGE pixel coordinate."""
    mapping = inspect_spectral_mapping(product)
    if mapping.status is not SpectralMappingStatus.VALID:
        return SpectralPixelResult(mapping.status, x, y, warning=mapping.warning)
    if not product.image_shape or not (0 <= x < product.image_shape[1] and 0 <= y < product.image_shape[0]):
        return SpectralPixelResult(SpectralMappingStatus.OUTSIDE_SUPPORTED_DOMAIN, x, y, warning="Pixel is outside this IMAGE/cutout.")
    try:
        with _open(product) as hdul:
            wcs = spectral_wcs(hdul)
            wavelength, bandwidth = wcs.all_pix2world([[x, y]], 0)[0]
        if not np.isfinite(wavelength) or not np.isfinite(bandwidth):
            return SpectralPixelResult(SpectralMappingStatus.OUTSIDE_SUPPORTED_DOMAIN, x, y, warning="WCS-WAVE has no tabular support at this pixel.")
        return SpectralPixelResult(SpectralMappingStatus.VALID, x, y, float(wavelength), float(bandwidth))
    except Exception as exc:
        return SpectralPixelResult(SpectralMappingStatus.MALFORMED, x, y, warning=str(exc))
