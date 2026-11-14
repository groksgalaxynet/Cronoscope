"""Small JSON-safe contracts shared by the future pipeline and web adapter."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


@dataclass(frozen=True)
class DiscoveryQuery:
    """A spatial search sent to the public SPHEREx SIA2 service."""

    ra_deg: float
    dec_deg: float
    radius_deg: float
    collection: str = "spherex_qr2"
    calibration_level: int | None = 2
    label: str | None = None


@dataclass(frozen=True)
class ObservationRecord:
    """Normalized SIA2 observation metadata; absent service fields remain None."""

    observation_id: str | None
    ra_deg: float | None
    dec_deg: float | None
    t_min_mjd: float | None
    t_max_mjd: float | None
    wavelength_min_m: float | None
    wavelength_max_m: float | None
    band_label: str | None
    calibration_level: int | None
    data_product_type: str | None
    access_url: str | None
    access_format: str | None
    access_estsize_kb: float | None
    collection: str | None
    instrument_name: str | None
    target_name: str | None
    s_region: str | None
    source_query: str | None = None
    raw_identifiers: dict[str, str] = field(default_factory=dict)

    def to_jsonable(self) -> dict[str, Any]:
        """Return only standard JSON types for a later HTTP/UI boundary."""
        return asdict(self)


class RetrievalStatus(str, Enum):
    SUCCESS = "SUCCESS"
    CACHE_HIT = "CACHE_HIT"
    NETWORK_ERROR = "NETWORK_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    INVALID_CONTENT = "INVALID_CONTENT"
    INVALID_FITS = "INVALID_FITS"
    IO_ERROR = "IO_ERROR"


class WcsStatus(str, Enum):
    VALID = "VALID"
    MISSING = "MISSING"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"


class ContainmentStatus(str, Enum):
    INSIDE = "INSIDE"
    OUTSIDE = "OUTSIDE"
    BOUNDARY = "BOUNDARY"
    INVALID_COORDINATE = "INVALID_COORDINATE"
    MISSING_WCS = "MISSING_WCS"
    INVALID_WCS = "INVALID_WCS"
    TRANSFORM_ERROR = "TRANSFORM_ERROR"


class TemporalStatus(str, Enum):
    MATCH = "MATCH"
    OUTSIDE_TOLERANCE = "OUTSIDE_TOLERANCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class FitsValidation:
    valid: bool
    hdu_count: int | None
    message: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalResult:
    status: RetrievalStatus
    cache_identity: str
    cache_path: str | None
    source_url: str | None
    bytes_written: int | None
    observation_id: str | None
    validation: FitsValidation | None
    message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status in {RetrievalStatus.SUCCESS, RetrievalStatus.CACHE_HIT}

    def to_jsonable(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass(frozen=True)
class HduInventoryEntry:
    index: int
    extname: str | None
    hdu_type: str
    shape: tuple[int, ...] | None
    bitpix: int | None
    has_image_data: bool
    has_celestial_wcs: bool

    def to_jsonable(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["shape"] = None if self.shape is None else list(self.shape)
        return payload


@dataclass(frozen=True)
class NormalizedFitsProduct:
    cache_identity: str
    cache_path: str
    selected_hdu_index: int | None
    selected_extname: str | None
    image_shape: tuple[int, ...] | None
    image: Any = field(repr=False, compare=False, default=None)
    wcs: Any = field(repr=False, compare=False, default=None)
    wcs_status: WcsStatus = WcsStatus.MISSING
    celestial_footprint_deg: tuple[tuple[float, float], ...] | None = None
    archive_timing_mjd: tuple[float | None, float | None] | None = None
    fits_timing: dict[str, Any] = field(default_factory=dict)
    archive_detector: str | None = None
    fits_detector: str | None = None
    archive_wavelength_m: tuple[float | None, float | None] | None = None
    fits_spectral_metadata: dict[str, Any] = field(default_factory=dict)
    hdu_inventory: tuple[HduInventoryEntry, ...] = ()
    warnings: tuple[str, ...] = ()
    observation_id: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "cache_identity": self.cache_identity,
            "cache_path": self.cache_path,
            "observation_id": self.observation_id,
            "selected_hdu_index": self.selected_hdu_index,
            "selected_extname": self.selected_extname,
            "image_shape": None if self.image_shape is None else list(self.image_shape),
            "image_available": self.image is not None,
            "wcs_status": self.wcs_status.value,
            "celestial_footprint_deg": self.celestial_footprint_deg,
            "archive_timing_mjd": self.archive_timing_mjd,
            "fits_timing": self.fits_timing,
            "archive_detector": self.archive_detector,
            "fits_detector": self.fits_detector,
            "archive_wavelength_m": self.archive_wavelength_m,
            "fits_spectral_metadata": self.fits_spectral_metadata,
            "hdu_inventory": [item.to_jsonable() for item in self.hdu_inventory],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ContainmentResult:
    status: ContainmentStatus
    inside: bool | None
    requested_ra_deg: float | None
    requested_dec_deg: float | None
    pixel_x: float | None
    pixel_y: float | None
    image_width: int | None
    image_height: int | None
    nearest_edge_distance_px: float | None
    cache_identity: str
    observation_id: str | None
    wcs_status: WcsStatus
    reason: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["wcs_status"] = self.wcs_status.value
        return payload


@dataclass(frozen=True)
class EphemerisMatch:
    object_name: str | None
    ephemeris_mjd: float | None
    containment: ContainmentResult
    observation_mjd: float | None
    time_offset_seconds: float | None
    temporal_status: TemporalStatus

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "object_name": self.object_name,
            "ephemeris_mjd": self.ephemeris_mjd,
            "containment": self.containment.to_jsonable(),
            "observation_mjd": self.observation_mjd,
            "time_offset_seconds": self.time_offset_seconds,
            "temporal_status": self.temporal_status.value,
        }


@dataclass(frozen=True)
class EpochGroup:
    """One archive observation ID and its available detector/wavelength products."""

    observation_id: str
    start_mjd: float | None
    end_mjd: float | None
    bands: tuple[ObservationRecord, ...]

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "start_mjd": self.start_mjd,
            "end_mjd": self.end_mjd,
            "bands": [record.to_jsonable() for record in self.bands],
        }


@dataclass(frozen=True)
class SkyAreaGroup:
    """A metadata-derived area bucket; it is not an exact footprint assertion."""

    area_key: str
    epochs: tuple[EpochGroup, ...]
    warnings: tuple[str, ...] = ()

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "area_key": self.area_key,
            "epochs": [epoch.to_jsonable() for epoch in self.epochs],
            "warnings": list(self.warnings),
        }
