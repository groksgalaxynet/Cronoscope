"""Small application-facing adapters for verified SPHEREx science products.

This module does not discover, calibrate, or alter observations.  It projects
an existing :class:`NormalizedFitsProduct` into bounded display data and pixel
readouts while preserving the distinction between a local WCS-WAVE wavelength
context and an extracted astronomical spectrum.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

import numpy as np
from astropy.io import fits

from .models import NormalizedFitsProduct, WcsStatus
from .spectral import (SpectralMappingStatus, SpectralPixelResult, inspect_spectral_mapping,
                       spectral_wcs, wavelength_at_pixel)


class VisualizationStatus(str, Enum):
    READY = "READY"
    INVALID_PRODUCT = "INVALID_PRODUCT"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"


@dataclass(frozen=True)
class IntensityScale:
    method: str
    lower_percentile: float
    upper_percentile: float
    low_value: float | None
    high_value: float | None
    display_unit: str
    warning: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VisualizationProduct:
    """Bounded grayscale representation; ``science_image`` remains local-only."""

    status: VisualizationStatus
    product: dict[str, Any]
    image_unit: str | None
    finite_pixel_count: int
    invalid_pixel_count: int
    flags_available: bool
    variance_available: bool
    intensity_scale: IntensityScale | None
    display_raster: np.ndarray | None = None
    science_image: np.ndarray | None = None
    warning: str | None = None

    def to_jsonable(self, *, include_display_raster: bool = True) -> dict[str, Any]:
        payload = {
            "status": self.status.value,
            "product": self.product,
            "image_unit": self.image_unit,
            "finite_pixel_count": self.finite_pixel_count,
            "invalid_pixel_count": self.invalid_pixel_count,
            "flags_available": self.flags_available,
            "variance_available": self.variance_available,
            "intensity_scale": None if self.intensity_scale is None else self.intensity_scale.to_jsonable(),
            "warning": self.warning,
            "display_kind": "GRAYSCALE_DISPLAY_STRETCH",
            "science_image_serialized": False,
        }
        if include_display_raster and self.display_raster is not None:
            payload["display_raster_uint8"] = self.display_raster.tolist()
        return payload


@dataclass(frozen=True)
class PixelReadout:
    status: str
    x: float
    y: float
    ra_deg: float | None
    dec_deg: float | None
    science_value: float | None
    science_value_valid: bool | None
    image_unit: str | None
    variance: float | None
    variance_available: bool
    quality_flags: int | float | None
    flags_available: bool
    wavelength_context: SpectralPixelResult
    warning: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "x": self.x,
            "y": self.y,
            "ra_deg": self.ra_deg,
            "dec_deg": self.dec_deg,
            "science_value": self.science_value,
            "science_value_valid": self.science_value_valid,
            "image_unit": self.image_unit,
            "variance": self.variance,
            "variance_available": self.variance_available,
            "quality_flags": self.quality_flags,
            "flags_available": self.flags_available,
            "wavelength_context": self.wavelength_context.to_jsonable(),
            "wavelength_context_is_not_source_spectrum": True,
            "warning": self.warning,
        }


@dataclass(frozen=True)
class WavelengthHighlight:
    status: SpectralMappingStatus
    target_wavelength_um: float
    tolerance_um: float
    matching_pixels: tuple[tuple[int, int], ...]
    matching_pixel_count: int
    truncated: bool
    warning: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "target_wavelength_um": self.target_wavelength_um,
            "tolerance_um": self.tolerance_um,
            "matching_pixels": [{"x": x, "y": y} for x, y in self.matching_pixels],
            "matching_pixel_count": self.matching_pixel_count,
            "truncated": self.truncated,
            "wavelength_context_is_not_source_spectrum": True,
            "warning": self.warning,
        }


def _extension_present(product: NormalizedFitsProduct, name: str) -> bool:
    return any((entry.extname or "").upper() == name for entry in product.hdu_inventory)


def _image_unit(product: NormalizedFitsProduct) -> str | None:
    try:
        with fits.open(product.cache_path, memmap=True) as hdul:
            hdu = hdul[product.selected_hdu_index] if product.selected_hdu_index is not None else None
            return None if hdu is None or hdu.header.get("BUNIT") is None else str(hdu.header["BUNIT"])
    except (OSError, IndexError, KeyError):
        return None


def visualization_product(product: NormalizedFitsProduct, *, max_pixels: int = 262_144) -> VisualizationProduct:
    """Create a bounded grayscale display raster from an existing science image.

    Display scaling is a 1st-to-99th percentile stretch of finite image pixels.
    No calibration, photometry, color mapping, or interpretation is inferred.
    """
    metadata = product.to_jsonable()
    if product.image is None or not product.image_shape or len(product.image_shape) != 2:
        return VisualizationProduct(VisualizationStatus.INVALID_PRODUCT, metadata, None, 0, 0, _extension_present(product, "FLAGS"),
                                    _extension_present(product, "VARIANCE"), None, warning="Product has no selected 2-D science image.")
    image = np.asarray(product.image, dtype=float)
    if image.size > max_pixels:
        return VisualizationProduct(VisualizationStatus.IMAGE_TOO_LARGE, metadata, _image_unit(product), 0, 0,
                                    _extension_present(product, "FLAGS"), _extension_present(product, "VARIANCE"), None,
                                    warning=f"Image has {image.size} pixels; bounded display limit is {max_pixels}.")
    finite = np.isfinite(image)
    finite_count = int(np.count_nonzero(finite))
    invalid_count = int(image.size - finite_count)
    unit = _image_unit(product)
    if finite_count == 0:
        scale = IntensityScale("percentile_linear", 1.0, 99.0, None, None, unit or "unknown", "No finite science pixels.")
        return VisualizationProduct(VisualizationStatus.INVALID_PRODUCT, metadata, unit, finite_count, invalid_count,
                                    _extension_present(product, "FLAGS"), _extension_present(product, "VARIANCE"), scale,
                                    warning="No finite science pixels are available for display.")
    values = image[finite]
    low, high = (float(value) for value in np.percentile(values, (1.0, 99.0)))
    raster = np.zeros(image.shape, dtype=np.uint8)
    warning = None
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        raster[finite] = 128
        warning = "Finite science values have no nonzero percentile display range; finite pixels use neutral gray."
    else:
        raster[finite] = np.rint(np.clip((image[finite] - low) / (high - low), 0.0, 1.0) * 255.0).astype(np.uint8)
    scale = IntensityScale("percentile_linear", 1.0, 99.0, low, high, unit or "unknown", warning)
    return VisualizationProduct(VisualizationStatus.READY, metadata, unit, finite_count, invalid_count,
                                _extension_present(product, "FLAGS"), _extension_present(product, "VARIANCE"), scale,
                                display_raster=raster, science_image=image, warning=warning)


def pixel_readout(product: NormalizedFitsProduct, x: float, y: float) -> PixelReadout:
    """Return a pixel's sky coordinate, value, and local WCS-WAVE context."""
    spectral = wavelength_at_pixel(product, x, y)
    unit = _image_unit(product)
    flags_available, variance_available = _extension_present(product, "FLAGS"), _extension_present(product, "VARIANCE")
    if product.image is None or not product.image_shape or not (0 <= x < product.image_shape[1] and 0 <= y < product.image_shape[0]):
        return PixelReadout("OUTSIDE_IMAGE", x, y, None, None, None, None, unit, None, variance_available, None, flags_available,
                            spectral, "Pixel is outside the selected IMAGE.")
    ix, iy = int(round(x)), int(round(y))
    if not (0 <= ix < product.image_shape[1] and 0 <= iy < product.image_shape[0]):
        return PixelReadout("OUTSIDE_IMAGE", x, y, None, None, None, None, unit, None, variance_available, None, flags_available,
                            spectral, "Rounded pixel is outside the selected IMAGE.")
    value = float(np.asarray(product.image, dtype=float)[iy, ix])
    variance, flags = _auxiliary_values(product, ix, iy)
    if product.wcs is None or product.wcs_status is not WcsStatus.VALID:
        return PixelReadout("WCS_UNAVAILABLE", x, y, None, None, value if np.isfinite(value) else None, bool(np.isfinite(value)), unit,
                            variance, variance_available, flags, flags_available, spectral,
                            "Celestial WCS is unavailable or invalid.")
    try:
        ra, dec = (float(item) for item in product.wcs.pixel_to_world_values(x, y))
    except Exception as exc:
        return PixelReadout("WCS_TRANSFORM_ERROR", x, y, None, None, value if np.isfinite(value) else None, bool(np.isfinite(value)), unit,
                            variance, variance_available, flags, flags_available, spectral,
                            f"Pixel-to-sky conversion failed: {exc}")
    if not np.isfinite(ra) or not np.isfinite(dec):
        return PixelReadout("WCS_TRANSFORM_ERROR", x, y, None, None, value if np.isfinite(value) else None, bool(np.isfinite(value)), unit,
                            variance, variance_available, flags, flags_available, spectral,
                            "Pixel-to-sky conversion returned non-finite coordinates.")
    return PixelReadout("READY", x, y, ra % 360.0, dec, value if np.isfinite(value) else None, bool(np.isfinite(value)), unit,
                        variance, variance_available, flags, flags_available, spectral)


def _auxiliary_values(product: NormalizedFitsProduct, x: int, y: int) -> tuple[float | None, int | float | None]:
    """Read colocated raw VARIANCE/FLAGS values without assigning bit semantics."""
    try:
        with fits.open(product.cache_path, memmap=True) as hdul:
            def value(name: str) -> float | None:
                if name not in hdul:
                    return None
                data = np.asarray(hdul[name].data)
                if data.ndim != 2 or y >= data.shape[0] or x >= data.shape[1]:
                    return None
                item = float(data[y, x])
                return item if np.isfinite(item) else None
            variance = value("VARIANCE")
            flag_value = value("FLAGS")
            if flag_value is not None and float(flag_value).is_integer():
                return variance, int(flag_value)
            return variance, flag_value
    except (OSError, KeyError, IndexError, TypeError, ValueError):
        return None, None


def highlight_wavelength_context(
    product: NormalizedFitsProduct,
    target_wavelength_um: float,
    tolerance_um: float,
    *,
    max_pixels: int = 262_144,
    max_matches: int = 10_000,
) -> WavelengthHighlight:
    """Return bounded IMAGE pixels whose local WCS-WAVE context matches a band.

    The result is a geometric display aid.  It neither resamples the image nor
    represents a wavelength-selected source spectrum or calibrated composite.
    """
    if not math_isfinite_positive(target_wavelength_um) or not math_isfinite_positive(tolerance_um):
        raise ValueError("target_wavelength_um and tolerance_um must be finite and positive")
    mapping = inspect_spectral_mapping(product)
    if mapping.status is not SpectralMappingStatus.VALID:
        return WavelengthHighlight(mapping.status, target_wavelength_um, tolerance_um, (), 0, False, mapping.warning)
    if product.image_shape is None or int(np.prod(product.image_shape)) > max_pixels:
        return WavelengthHighlight(SpectralMappingStatus.OUTSIDE_SUPPORTED_DOMAIN, target_wavelength_um, tolerance_um, (), 0, False,
                                   f"Image exceeds bounded wavelength-highlight limit of {max_pixels} pixels.")
    height, width = product.image_shape
    try:
        with fits.open(product.cache_path, memmap=True) as hdul:
            wcs = spectral_wcs(hdul)
            yy, xx = np.indices((height, width), dtype=float)
            coordinates = np.column_stack((xx.ravel(), yy.ravel()))
            wavelengths = np.asarray(wcs.all_pix2world(coordinates, 0), dtype=float)[:, 0].reshape((height, width))
    except Exception as exc:
        return WavelengthHighlight(SpectralMappingStatus.MALFORMED, target_wavelength_um, tolerance_um, (), 0, False, str(exc))
    matches = np.argwhere(np.isfinite(wavelengths) & (np.abs(wavelengths - target_wavelength_um) <= tolerance_um))
    pixels = tuple((int(x), int(y)) for y, x in matches[:max_matches])
    return WavelengthHighlight(SpectralMappingStatus.VALID, target_wavelength_um, tolerance_um, pixels, int(len(matches)), len(matches) > max_matches)


def math_isfinite_positive(value: float) -> bool:
    return bool(np.isfinite(value) and value > 0)
