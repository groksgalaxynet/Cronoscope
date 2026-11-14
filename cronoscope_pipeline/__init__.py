"""Offline-testable SPHEREx data-pipeline foundations for Cronoscope."""

from .discovery import DiscoveryError, discover_observations, parse_votable_bytes
from .grouping import group_observations
from .fits_normalization import normalize_fits_product
from .footprint import contains_sky_coordinate, match_ephemeris_to_product
from .comparison import compare_observations, FROZEN_TEST5_TEST7_V1
from .orchestrator import CronoscopeOrchestrator, public_product_id
from .models import (ContainmentStatus, DiscoveryQuery, ObservationRecord,
                     RetrievalStatus, TemporalStatus, WcsStatus)
from .retrieval import retrieve_product
from .observer_population import HorizonsEphemerisResponse, HorizonsTransportStatus, request_horizons_ephemeris
from .science_interface import (PixelReadout, VisualizationProduct, VisualizationStatus,
                                WavelengthHighlight, highlight_wavelength_context, pixel_readout,
                                visualization_product)

__all__ = [
    "DiscoveryError",
    "DiscoveryQuery",
    "ObservationRecord",
    "RetrievalStatus",
    "WcsStatus",
    "ContainmentStatus",
    "TemporalStatus",
    "discover_observations",
    "group_observations",
    "parse_votable_bytes",
    "retrieve_product",
    "normalize_fits_product",
    "contains_sky_coordinate",
    "match_ephemeris_to_product",
    "compare_observations",
    "FROZEN_TEST5_TEST7_V1",
    "CronoscopeOrchestrator",
    "public_product_id",
    "HorizonsEphemerisResponse",
    "HorizonsTransportStatus",
    "request_horizons_ephemeris",
    "VisualizationStatus",
    "VisualizationProduct",
    "PixelReadout",
    "WavelengthHighlight",
    "visualization_product",
    "pixel_readout",
    "highlight_wavelength_context",
]
