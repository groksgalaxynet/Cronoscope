"""Validated, injectable SPHEREx FITS retrieval with collision-safe caching."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

import requests
from astropy.io import fits

from .models import FitsValidation, ObservationRecord, RetrievalResult, RetrievalStatus


class ResponseLike(Protocol):
    status_code: int
    content: bytes
    headers: dict[str, str]


def cache_identity(observation: ObservationRecord) -> str:
    """Derive a stable identity from scientific/native metadata plus source URL.

    The readable prefix is the native observation and detector. A SHA-256
    suffix includes publisher identity, wavelength bounds, and URL, preventing
    same-basename products from overwriting scientifically distinct products.
    """
    obs_id = observation.observation_id or "unknown-observation"
    detector = observation.band_label or "unknown-band"
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", f"{obs_id}_{detector}")
    parts = [
        observation.raw_identifiers.get("obs_publisher_did", ""), observation.observation_id or "",
        observation.band_label or "", repr(observation.wavelength_min_m), repr(observation.wavelength_max_m),
        observation.access_url or "",
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{safe_prefix}_{digest}"


def cache_path_for(observation: ObservationRecord, cache_dir: str | Path) -> Path:
    return Path(cache_dir) / f"{cache_identity(observation)}.fits"


def validate_fits_file(path: str | Path) -> FitsValidation:
    path = Path(path)
    if not path.is_file() or path.stat().st_size == 0:
        return FitsValidation(False, None, "file is missing or empty")
    try:
        with fits.open(path, memmap=False) as hdul:
            if len(hdul) == 0:
                return FitsValidation(False, 0, "FITS contains no HDUs")
            for hdu in hdul:
                _ = hdu.header.cards  # force header parsing for every HDU
            return FitsValidation(True, len(hdul))
    except Exception as exc:  # Astropy parser exception hierarchy varies
        return FitsValidation(False, None, f"FITS validation failed: {exc}")


def _fits_compatible(access_format: str | None) -> bool:
    return bool(access_format and ("fits" in access_format.lower() or "x-fits" in access_format.lower()))


def _result(status: RetrievalStatus, observation: ObservationRecord, identity: str, **kwargs: object) -> RetrievalResult:
    return RetrievalResult(status=status, cache_identity=identity, observation_id=observation.observation_id,
                           source_url=observation.access_url, **kwargs)


def retrieve_product(
    observation: ObservationRecord,
    cache_dir: str | Path,
    *,
    session: requests.Session | None = None,
    timeout_seconds: float = 90,
) -> RetrievalResult:
    """Return a validated cache hit or atomically retrieve one FITS product."""
    identity = cache_identity(observation)
    if not observation.access_url:
        return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=None, bytes_written=None,
                       validation=None, message="Observation has no access_url")
    if not _fits_compatible(observation.access_format):
        return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=None, bytes_written=None,
                       validation=None, message="Observation access_format is not FITS-compatible")

    final_path = cache_path_for(observation, cache_dir)
    try:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        existing = validate_fits_file(final_path)
        if existing.valid:
            return _result(RetrievalStatus.CACHE_HIT, observation, identity, cache_path=str(final_path),
                           bytes_written=final_path.stat().st_size, validation=existing)
    except OSError as exc:
        return _result(RetrievalStatus.IO_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, message=str(exc))

    client = session or requests.Session()
    if isinstance(client, requests.Session):
        client.max_redirects = 3
    try:
        response = client.get(observation.access_url, timeout=timeout_seconds, allow_redirects=True)
    except requests.RequestException as exc:
        return _result(RetrievalStatus.NETWORK_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, message=str(exc))
    if not 200 <= response.status_code < 300:
        return _result(RetrievalStatus.HTTP_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, message=f"HTTP {response.status_code}")
    content = response.content
    reported_length = response.headers.get("Content-Length")
    if reported_length is not None:
        try:
            if int(reported_length) != len(content):
                return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=str(final_path), bytes_written=None,
                               validation=None, message="Content-Length does not match downloaded bytes")
        except ValueError:
            return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=str(final_path), bytes_written=None,
                           validation=None, message="Response has a non-numeric Content-Length")
    if not content or content.lstrip().lower().startswith((b"<!doctype html", b"<html", b"<?xml")):
        return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, message="response is empty or appears to be text/HTML/XML, not FITS")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=final_path.parent, prefix=f".{identity}.", suffix=".part", delete=False) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        validation = validate_fits_file(temporary_path)
        if not validation.valid:
            return _result(RetrievalStatus.INVALID_FITS, observation, identity, cache_path=str(final_path), bytes_written=None,
                           validation=validation, message=validation.message)
        os.replace(temporary_path, final_path)
        temporary_path = None
        return _result(RetrievalStatus.SUCCESS, observation, identity, cache_path=str(final_path),
                       bytes_written=final_path.stat().st_size, validation=validation)
    except OSError as exc:
        return _result(RetrievalStatus.IO_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, message=str(exc))
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
