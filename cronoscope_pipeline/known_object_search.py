"""Neutral parsing and query construction for known-object field searches."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SB_IDENT_URL = "https://ssd-api.jpl.nasa.gov/sb_ident.api"


@dataclass(frozen=True)
class KnownObjectSearchQuery:
    mjd_utc: float
    ra_deg: float
    dec_deg: float
    ra_halfwidth_deg: float
    dec_halfwidth_deg: float
    xobs_icrf_km_km_s: tuple[float, float, float, float, float, float]

    def params(self) -> dict[str, str]:
        def ra(value: float) -> str:
            value /= 15.0; hour = int(value); minute = int((value - hour) * 60); second = ((value - hour) * 60 - minute) * 60
            return f"{hour:02d}-{minute:02d}-{second:06.3f}"
        def dec(value: float) -> str:
            sign = "+" if value >= 0 else "M"; value = abs(value); degree = int(value); minute = int((value - degree) * 60); second = ((value - degree) * 60 - minute) * 60
            return f"{sign}{degree:02d}-{minute:02d}-{second:06.3f}"
        return {"xobs": ",".join(f"{value:.12g}" for value in self.xobs_icrf_km_km_s), "obs-time": f"{self.mjd_utc + 2400000.5:.9f}",
                "fov-ra-center": ra(self.ra_deg % 360), "fov-dec-center": dec(self.dec_deg),
                "fov-ra-hwidth": f"{self.ra_halfwidth_deg:.9f}", "fov-dec-hwidth": f"{self.dec_halfwidth_deg:.9f}",
                "two-pass": "true", "suppress-first-pass": "true", "mag-required": "false", "req-elem": "false"}


@dataclass(frozen=True)
class KnownObjectCandidate:
    raw_identifier: str
    ra_text: str | None
    dec_text: str | None
    magnitude: str | None
    ra_rate: str | None
    dec_rate: str | None
    provider: str = "NASA/JPL Small-Body Identification API"
    observer_semantics: str = "explicit ICRF geocentric spacecraft state vector (xobs)"

    def jsonable(self) -> dict[str, Any]: return asdict(self)


def parse_sb_ident(payload: dict[str, Any]) -> list[KnownObjectCandidate]:
    signature = payload.get("signature", {})
    if signature.get("source") != "NASA/JPL Small-Body Identification API":
        raise ValueError("unexpected SB Identification API provenance")
    fields = payload.get("fields_second", payload.get("fields_first", []))
    data = payload.get("data_second_pass", payload.get("data_first_pass", []))
    if not isinstance(fields, list) or not isinstance(data, list): raise ValueError("malformed SB Identification response")
    lookup = {str(name): index for index, name in enumerate(fields)}
    candidates = []
    for row in data:
        if not isinstance(row, list) or not row or not str(row[0]).strip(): continue
        value = lambda key: str(row[lookup[key]]) if key in lookup and lookup[key] < len(row) else None
        candidates.append(KnownObjectCandidate(str(row[0]), value("Astrometric RA (hh:mm:ss)"), value("Astrometric Dec (dd mm'ss\")"),
                                               value("Visual magnitude (V)"), value("RA rate (deg/s)"), value("Dec rate (deg/s)")))
    return candidates
