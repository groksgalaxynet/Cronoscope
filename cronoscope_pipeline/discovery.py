"""SPHEREx SIA2 discovery transport and VOTable normalization.

Transport is intentionally separate from parsing so saved VOTables exercise the
same normalization path as a live request.
"""

from __future__ import annotations

from io import BytesIO
import numpy as np
import requests
from astropy.io.votable import parse

from .models import DiscoveryQuery, ObservationRecord

SIA2_URL = "https://irsa.ipac.caltech.edu/SIA"
DEFAULT_COLLECTION = "spherex_qr2"
SUPPORTED_COLLECTIONS = frozenset({"spherex_qr2", "spherex_qr3"})


class DiscoveryError(RuntimeError):
    """A transport or parse error that does not imply a scientific result."""


def validate_collection(collection: object) -> str:
    """Return an explicit supported archive collection or reject it."""
    if not isinstance(collection, str) or collection not in SUPPORTED_COLLECTIONS:
        raise ValueError("collection must be one of: spherex_qr2, spherex_qr3")
    return collection


def build_sia2_params(query: DiscoveryQuery) -> dict[str, str]:
    if not (0.0 <= query.ra_deg < 360.0):
        raise ValueError("ra_deg must be in [0, 360)")
    if not (-90.0 <= query.dec_deg <= 90.0):
        raise ValueError("dec_deg must be in [-90, 90]")
    if query.radius_deg <= 0:
        raise ValueError("radius_deg must be positive")
    collection = validate_collection(query.collection)

    params = {
        "COLLECTION": collection,
        "POS": f"CIRCLE {query.ra_deg} {query.dec_deg} {query.radius_deg}",
        "RESPONSEFORMAT": "votable",
    }
    if query.calibration_level is not None:
        params["CALIB"] = str(query.calibration_level)
    return params


def fetch_votable(
    query: DiscoveryQuery,
    *,
    session: requests.Session | None = None,
    timeout_seconds: float = 90,
) -> bytes:
    """Fetch raw VOTable bytes only; callers may save them for offline replay."""
    client = session or requests.Session()
    try:
        response = client.get(SIA2_URL, params=build_sia2_params(query), timeout=timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise DiscoveryError(f"SPHEREx SIA2 transport failed: {exc}") from exc
    if not response.content.lstrip().startswith(b"<?xml"):
        raise DiscoveryError("SPHEREx SIA2 response was not a VOTable XML document")
    return response.content


def discover_observations(
    ra_deg: float,
    dec_deg: float,
    radius_deg: float,
    *,
    label: str | None = None,
    collection: str = DEFAULT_COLLECTION,
    calibration_level: int | None = 2,
    session: requests.Session | None = None,
    timeout_seconds: float = 90,
) -> list[ObservationRecord]:
    """Live convenience wrapper; parsing remains independently testable."""
    query = DiscoveryQuery(ra_deg, dec_deg, radius_deg, validate_collection(collection), calibration_level, label)
    return parse_votable_bytes(fetch_votable(query, session=session, timeout_seconds=timeout_seconds), query)


def _clean(value: object) -> str | None:
    if value is None or np.ma.is_masked(value):
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    text = str(value).strip()
    return text or None


def _number(value: object) -> float | None:
    text = _clean(value)
    if text is None:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _semantic_columns(table_element: object) -> dict[str, str]:
    columns: dict[str, str] = {}
    for field in table_element.fields:
        if field.name is not None and field.ID is not None:
            columns[str(field.name)] = str(field.ID)
    return columns


def parse_votable_bytes(content: bytes, query: DiscoveryQuery | None = None) -> list[ObservationRecord]:
    """Normalize an SIA2 VOTable without requiring network access."""
    try:
        table_element = parse(BytesIO(content)).get_first_table()
        table = table_element.to_table(use_names_over_ids=False)
    except Exception as exc:  # astropy has several parser exception classes
        raise DiscoveryError(f"Could not parse SIA2 VOTable: {exc}") from exc

    names = _semantic_columns(table_element)

    def value(row: object, name: str) -> object | None:
        column = names.get(name)
        return None if column is None or column not in row.colnames else row[column]

    records: list[ObservationRecord] = []
    for row in table:
        raw_identifiers = {
            name: cleaned
            for name in ("obs_publisher_did", "obs_creator_did", "spherex_uuid")
            if (cleaned := _clean(value(row, name))) is not None
        }
        calib = _number(value(row, "calib_level"))
        records.append(ObservationRecord(
            observation_id=_clean(value(row, "obs_id")),
            ra_deg=_number(value(row, "s_ra")), dec_deg=_number(value(row, "s_dec")),
            t_min_mjd=_number(value(row, "t_min")), t_max_mjd=_number(value(row, "t_max")),
            wavelength_min_m=_number(value(row, "em_min")), wavelength_max_m=_number(value(row, "em_max")),
            band_label=_clean(value(row, "energy_bandpassname")) or _clean(value(row, "spherex_detector")),
            calibration_level=None if calib is None else int(calib),
            data_product_type=_clean(value(row, "dataproduct_type")),
            access_url=_clean(value(row, "access_url")), access_format=_clean(value(row, "access_format")),
            access_estsize_kb=_number(value(row, "access_estsize")),
            collection=_clean(value(row, "obs_collection")), instrument_name=_clean(value(row, "instrument_name")),
            target_name=_clean(value(row, "target_name")), s_region=_clean(value(row, "s_region")),
            source_query=None if query is None else query.label,
            raw_identifiers=raw_identifiers,
        ))
    return records
