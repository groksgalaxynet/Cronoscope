"""Reusable, deterministic helpers for a Horizons observer-population run."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import io
import math
from typing import Any, Iterable

import requests


EARTH_CENTER = "500@399"
SPHEREX_CENTER = "500@-163182"
SPHEREX_ID = "-163182"
MAX_EPOCHS_PER_REQUEST = 50
HORIZONS_FILE_API_URL = "https://ssd.jpl.nasa.gov/api/horizons_file.api"


class HorizonsTransportStatus(str, Enum):
    """Operational result of a bounded Horizons File API request.

    A successful transport is an ephemeris prediction only.  It is deliberately
    separate from image containment and never asserts an observation/detection.
    """

    SUCCESS = "SUCCESS"
    NETWORK_ERROR = "NETWORK_ERROR"
    HTTP_ERROR = "HTTP_ERROR"
    PARSE_ERROR = "PARSE_ERROR"


@dataclass(frozen=True)
class HorizonsEphemerisResponse:
    """Provenance-preserving result of one or more File API POST batches."""

    status: HorizonsTransportStatus
    object_name: str
    command: str
    observer_center: str
    requested_mjd: tuple[float, ...]
    rows: tuple[dict[str, object], ...] = ()
    request_sha256: tuple[str, ...] = ()
    service_url: str = HORIZONS_FILE_API_URL
    http_statuses: tuple[int, ...] = ()
    message: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        payload["requested_mjd"] = list(self.requested_mjd)
        payload["rows"] = [dict(row) for row in self.rows]
        payload["request_sha256"] = list(self.request_sha256)
        payload["http_statuses"] = list(self.http_statuses)
        payload["prediction_only"] = True
        return payload


def chunked(values: list[float], size: int = MAX_EPOCHS_PER_REQUEST) -> Iterable[list[float]]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for start in range(0, len(values), size):
        yield values[start:start + size]


def build_horizons_input(command: str, times: list[float], center: str) -> str:
    if not times:
        raise ValueError("cannot construct an empty Horizons request")
    if len(times) > MAX_EPOCHS_PER_REQUEST:
        raise ValueError("Horizons request exceeds 50-epoch batch limit")
    return "\n".join((
        "!$$SOF", f"COMMAND='{command}'", "OBJ_DATA='NO'", "MAKE_EPHEM='YES'",
        "TABLE_TYPE='OBSERVER'", f"CENTER='{center}'", "TLIST_TYPE='MJD'",
        "TLIST='" + ",".join(f"{value:.8f}" for value in times) + "'",
        "TIME_TYPE='UT'", "TIME_DIGITS='FRACSEC'", "CAL_FORMAT='BOTH'",
        "ANG_FORMAT='DEG'", "CSV_FORMAT='YES'", "QUANTITIES='1'", "!$$EOF", "",
    ))


def request_horizons_ephemeris(
    command: str,
    object_name: str,
    times_mjd: list[float],
    observer_center: str,
    *,
    session: requests.Session | None = None,
    timeout_seconds: float = 60.0,
    service_url: str = HORIZONS_FILE_API_URL,
) -> HorizonsEphemerisResponse:
    """Request bounded observer ephemerides through the Horizons File API.

    The API accepts a multipart ``input`` file.  Each request has at most 50
    epochs, follows the established command-file format, and is parsed by the
    existing semantic CSV parser.  Network results are explicit structured
    states so offline consumers can retain the deterministic parser path.
    """
    if not command.strip():
        raise ValueError("Horizons command must be non-empty")
    if not object_name.strip():
        raise ValueError("Horizons object_name must be non-empty")
    if not times_mjd:
        raise ValueError("cannot request an empty Horizons epoch list")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if any(not math.isfinite(float(value)) for value in times_mjd):
        raise ValueError("Horizons epochs must be finite MJD values")

    client = session or requests.Session()
    requested = tuple(float(value) for value in times_mjd)
    rows: list[dict[str, object]] = []
    request_hashes: list[str] = []
    http_statuses: list[int] = []
    for batch_index, batch in enumerate(chunked(list(requested))):
        request_text = build_horizons_input(command, batch, observer_center)
        request_hashes.append(hashlib.sha256(request_text.encode("utf-8")).hexdigest())
        try:
            response = client.post(
                service_url,
                data={"format": "text"},
                files={"input": ("cronoscope_horizons_input.txt", request_text, "text/plain")},
                timeout=timeout_seconds,
            )
        except requests.RequestException as exc:
            return HorizonsEphemerisResponse(HorizonsTransportStatus.NETWORK_ERROR, object_name, command, observer_center,
                                             requested, tuple(rows), tuple(request_hashes), service_url, tuple(http_statuses),
                                             f"Horizons File API transport failed: {exc}")
        http_statuses.append(int(response.status_code))
        if not 200 <= response.status_code < 300:
            return HorizonsEphemerisResponse(HorizonsTransportStatus.HTTP_ERROR, object_name, command, observer_center,
                                             requested, tuple(rows), tuple(request_hashes), service_url, tuple(http_statuses),
                                             f"Horizons File API returned HTTP {response.status_code}")
        try:
            parsed = parse_horizons_csv(response.text, object_name, command, observer_center)
            associate(batch, parsed)
        except (ValueError, AttributeError) as exc:
            return HorizonsEphemerisResponse(HorizonsTransportStatus.PARSE_ERROR, object_name, command, observer_center,
                                             requested, tuple(rows), tuple(request_hashes), service_url, tuple(http_statuses),
                                             f"Horizons File API response could not be validated: {exc}")
        for row in parsed:
            rows.append(dict(row) | {
                "source": "JPL Horizons File API",
                "transport": "MULTIPART_POST",
                "request_batch_index": batch_index,
                "request_sha256": request_hashes[-1],
                "prediction_only": True,
            })
    return HorizonsEphemerisResponse(HorizonsTransportStatus.SUCCESS, object_name, command, observer_center,
                                     requested, tuple(rows), tuple(request_hashes), service_url, tuple(http_statuses))


def _header(text: str) -> str:
    if "$$SOE" not in text or "$$EOE" not in text:
        raise ValueError("Horizons response lacks a complete ephemeris block")
    for line in reversed(text.split("$$SOE", 1)[0].splitlines()):
        upper = line.upper()
        if "," in line and "DEC" in upper and ("R.A." in upper or "RA" in upper):
            return line.strip()
    raise ValueError("Horizons response lacks semantic RA/Dec CSV header")


def parse_horizons_csv(text: str, object_name: str, command: str, observer: str) -> list[dict[str, object]]:
    header = _header(text)
    body = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    rows = list(csv.reader(io.StringIO(header + "\n" + "\n".join(
        line.strip() for line in body.splitlines() if line.strip() and "," in line))))
    columns = [cell.strip() for cell in rows[0]]
    jd = ra = dec = None
    for index, name in enumerate(columns):
        normalized = name.upper().replace(" ", "").replace("_", "")
        if jd is None and ("JDUT" in normalized or "JDTDB" in normalized or normalized.startswith("JD")):
            jd = index
        if ra is None and ("R.A." in name.upper() or normalized == "RA" or normalized.startswith("RA(")):
            ra = index
        if dec is None and "DEC" in normalized:
            dec = index
    if None in (jd, ra, dec):
        raise ValueError("Horizons semantic JD/RA/Dec columns unavailable")
    parsed = []
    for values in rows[1:]:
        if len(values) <= max(jd, ra, dec):
            continue
        try:
            value_jd, value_ra, value_dec = float(values[jd]), float(values[ra]), float(values[dec])
        except ValueError:
            continue
        parsed.append({"object": object_name, "command": command, "mjd": value_jd - 2400000.5,
                       "jd": value_jd, "ra_deg": value_ra, "dec_deg": value_dec,
                       "observer_center": observer})
    if not parsed:
        raise ValueError("Horizons response contained no numeric ephemeris rows")
    return parsed


def associate(requested: list[float], returned: list[dict[str, object]], tolerance_seconds: float = 5.0) -> float:
    """Require a unique return row for every requested epoch; return worst error."""
    if len(requested) != len(returned):
        raise ValueError(f"epoch count mismatch: {len(requested)} != {len(returned)}")
    unused = list(range(len(returned)))
    worst = 0.0
    for epoch in requested:
        best = min(unused, key=lambda index: abs(float(returned[index]["mjd"]) - epoch))
        error = abs(float(returned[best]["mjd"]) - epoch) * 86400.0
        if error > tolerance_seconds:
            raise ValueError(f"epoch mismatch: {error:.6f}s")
        unused.remove(best)
        worst = max(worst, error)
    return worst


def separation_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    r1, d1, r2, d2 = map(math.radians, (ra1, dec1, ra2, dec2))
    cosine = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine)))) * 3600.0
