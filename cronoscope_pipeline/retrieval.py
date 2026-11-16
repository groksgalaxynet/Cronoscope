"""Validated, injectable SPHEREx FITS retrieval with collision-safe caching."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from astropy.io import fits

from .models import FitsValidation, ObservationRecord, RetrievalResult, RetrievalStatus

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_CUTOUT_SIZE_DEG = 0.1
_CUTOUT_COLLECTIONS = frozenset({"spherex_dr1", "spherex_dr1_deep", "spherex_qr3"})
_DR1_IMAGE_COLLECTIONS = frozenset({"spherex_dr1", "spherex_dr1_deep"})
_DR1_REQUIRED_EXTENSIONS = frozenset({"IMAGE", "FLAGS", "VARIANCE", "ZODI", "EPSF", "WCS-WAVE"})


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
        observation.access_url or "", repr(observation.query_ra_deg), repr(observation.query_dec_deg),
        repr(observation.query_radius_deg),
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


def validate_dr1_image_file(path: str | Path) -> FitsValidation:
    """Validate the observed DR1 Level-2 spectral-image MEF contract."""
    path = Path(path)
    generic = validate_fits_file(path)
    if not generic.valid:
        return generic
    try:
        with fits.open(path, memmap=False) as hdul:
            named = {str(hdu.header.get("EXTNAME", "")).upper(): hdu for hdu in hdul}
            missing = sorted(_DR1_REQUIRED_EXTENSIONS - named.keys())
            if missing:
                return FitsValidation(False, len(hdul), f"DR1 image is missing required extensions: {', '.join(missing)}")
            image = named["IMAGE"]
            if getattr(image.data, "ndim", 0) != 2:
                return FitsValidation(False, len(hdul), "DR1 IMAGE extension must be two-dimensional")
            shape = tuple(image.data.shape)
            for name in ("FLAGS", "VARIANCE", "ZODI"):
                if getattr(named[name].data, "ndim", 0) != 2 or tuple(named[name].data.shape) != shape:
                    return FitsValidation(False, len(hdul), f"DR1 {name} must be a two-dimensional array aligned with IMAGE")
            if not image.header.get("BUNIT") or not named["VARIANCE"].header.get("BUNIT"):
                return FitsValidation(False, len(hdul), "DR1 IMAGE and VARIANCE units must be explicit")
            wave_names = set(getattr(named["WCS-WAVE"].data, "names", ()) or ())
            if not {"X", "Y", "VALUES"}.issubset(wave_names):
                return FitsValidation(False, len(hdul), "DR1 WCS-WAVE must contain X, Y, and VALUES columns")
            if getattr(named["EPSF"].data, "names", None) is None:
                return FitsValidation(False, len(hdul), "DR1 EPSF must be a binary table")
            return FitsValidation(True, len(hdul))
    except Exception as exc:
        return FitsValidation(False, generic.hdu_count, f"DR1 image validation failed: {exc}")


def _validate_for_observation(path: str | Path, observation: ObservationRecord) -> FitsValidation:
    if observation.collection in _DR1_IMAGE_COLLECTIONS:
        return validate_dr1_image_file(path)
    return validate_fits_file(path)


def _fits_compatible(access_format: str | None) -> bool:
    return bool(access_format and ("fits" in access_format.lower() or "x-fits" in access_format.lower()))


def bounded_access_url(observation: ObservationRecord) -> str | None:
    """Return a documented IRSA MEF cutout URL when query coordinates are available."""
    if not observation.access_url:
        return None
    parsed = urlparse(observation.access_url)
    is_irsa_mef = (parsed.hostname == "irsa.ipac.caltech.edu" and "/ibe/data/spherex/" in parsed.path
                   and observation.collection in _CUTOUT_COLLECTIONS and observation.data_product_type == "image")
    coordinates = (observation.query_ra_deg, observation.query_dec_deg, observation.query_radius_deg)
    if not is_irsa_mef or any(value is None for value in coordinates):
        return observation.access_url
    size = min(MAX_CUTOUT_SIZE_DEG, max(0.001, float(observation.query_radius_deg) * 2.0))
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"center": f"{observation.query_ra_deg},{observation.query_dec_deg}", "size": f"{size:.10g}"})
    return urlunparse(parsed._replace(query=urlencode(query)))


def _result(status: RetrievalStatus, observation: ObservationRecord, identity: str, **kwargs: object) -> RetrievalResult:
    source_url = kwargs.pop("source_url", observation.access_url)
    return RetrievalResult(status=status, cache_identity=identity, observation_id=observation.observation_id,
                           source_url=source_url, **kwargs)


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

    download_url = bounded_access_url(observation)
    final_path = cache_path_for(observation, cache_dir)
    try:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        existing = _validate_for_observation(final_path, observation)
        if existing.valid:
            return _result(RetrievalStatus.CACHE_HIT, observation, identity, cache_path=str(final_path),
                           bytes_written=final_path.stat().st_size, validation=existing, source_url=download_url)
    except OSError as exc:
        return _result(RetrievalStatus.IO_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, message=str(exc))

    parsed_url = urlparse(download_url or "")
    is_official_irsa = parsed_url.hostname == "irsa.ipac.caltech.edu"
    is_cutout = bool(parsed_url.query and {"center", "size"}.issubset(dict(parse_qsl(parsed_url.query))))
    if (is_official_irsa and not is_cutout and observation.access_estsize_kb is not None
            and observation.access_estsize_kb * 1024 > MAX_DOWNLOAD_BYTES):
        return _result(RetrievalStatus.SIZE_LIMIT_EXCEEDED, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, source_url=download_url,
                       message=f"Advertised product size exceeds the {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MiB download limit.")

    client = session or requests.Session()
    if isinstance(client, requests.Session):
        client.max_redirects = 3
    try:
        response = client.get(download_url, timeout=timeout_seconds, allow_redirects=True, stream=True)
    except requests.RequestException as exc:
        return _result(RetrievalStatus.NETWORK_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, source_url=download_url, message=str(exc))
    if not 200 <= response.status_code < 300:
        return _result(RetrievalStatus.HTTP_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, source_url=download_url, message=f"HTTP {response.status_code}")
    reported_length = response.headers.get("Content-Length")
    if reported_length is not None:
        try:
            if int(reported_length) > MAX_DOWNLOAD_BYTES:
                return _result(RetrievalStatus.SIZE_LIMIT_EXCEEDED, observation, identity, cache_path=str(final_path), bytes_written=None,
                               validation=None, source_url=download_url,
                               message=f"Response exceeds the {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MiB download limit.")
        except ValueError:
            return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=str(final_path), bytes_written=None,
                           validation=None, source_url=download_url, message="Response has a non-numeric Content-Length")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=final_path.parent, prefix=f".{identity}.", suffix=".part", delete=False) as handle:
            temporary_path = Path(handle.name)
            iterator = response.iter_content(chunk_size=1024 * 1024) if hasattr(response, "iter_content") else (response.content,)
            bytes_written, prefix = 0, b""
            for chunk in iterator:
                if not chunk:
                    continue
                bytes_written += len(chunk)
                if bytes_written > MAX_DOWNLOAD_BYTES:
                    return _result(RetrievalStatus.SIZE_LIMIT_EXCEEDED, observation, identity, cache_path=str(final_path), bytes_written=None,
                                   validation=None, source_url=download_url,
                                   message=f"Download exceeded the {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MiB limit.")
                if len(prefix) < 64:
                    prefix = (prefix + chunk)[:64]
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if reported_length is not None and int(reported_length) != bytes_written:
            return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=str(final_path), bytes_written=None,
                           validation=None, source_url=download_url, message="Content-Length does not match downloaded bytes")
        if bytes_written == 0 or prefix.lstrip().lower().startswith((b"<!doctype html", b"<html", b"<?xml")):
            return _result(RetrievalStatus.INVALID_CONTENT, observation, identity, cache_path=str(final_path), bytes_written=None,
                           validation=None, source_url=download_url,
                           message="response is empty or appears to be text/HTML/XML, not FITS")
        validation = _validate_for_observation(temporary_path, observation)
        if not validation.valid:
            return _result(RetrievalStatus.INVALID_FITS, observation, identity, cache_path=str(final_path), bytes_written=None,
                           validation=validation, source_url=download_url, message=validation.message)
        os.replace(temporary_path, final_path)
        temporary_path = None
        return _result(RetrievalStatus.SUCCESS, observation, identity, cache_path=str(final_path),
                       bytes_written=final_path.stat().st_size, validation=validation, source_url=download_url)
    except OSError as exc:
        return _result(RetrievalStatus.IO_ERROR, observation, identity, cache_path=str(final_path), bytes_written=None,
                       validation=None, source_url=download_url, message=str(exc))
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
