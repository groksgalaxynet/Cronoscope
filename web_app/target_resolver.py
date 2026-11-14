"""Bounded astronomical target-name resolution for the Observation Explorer."""

from __future__ import annotations

import math
import socket
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen
from xml.etree import ElementTree


@dataclass(frozen=True)
class TargetResolution:
    status: str
    query: str
    canonical_name: str | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None
    source: str | None = None
    cached: bool = False
    message: str | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {"status": self.status, "query": self.query, "canonical_name": self.canonical_name,
                "ra_deg": self.ra_deg, "dec_deg": self.dec_deg, "source": self.source,
                "cached": self.cached, "message": self.message}


def _key(value: str) -> str:
    return " ".join(value.casefold().split())


# ICRS/J2000 values are retained as an offline fallback for the common objects
# presented in the Observation Explorer.  They are never substituted for an
# unrecognised query.
LOCAL_TARGETS = {
    "m31": ("M 31 (Andromeda Galaxy)", 10.6847083, 41.26875),
    "andromeda": ("M 31 (Andromeda Galaxy)", 10.6847083, 41.26875),
    "andromeda galaxy": ("M 31 (Andromeda Galaxy)", 10.6847083, 41.26875),
    "ngc 224": ("M 31 (Andromeda Galaxy)", 10.6847083, 41.26875),
    "ngc224": ("M 31 (Andromeda Galaxy)", 10.6847083, 41.26875),
    "m87": ("M 87 (Virgo A)", 187.70593, 12.39112),
    "virgo a": ("M 87 (Virgo A)", 187.70593, 12.39112),
    "ngc 4486": ("M 87 (Virgo A)", 187.70593, 12.39112),
    "m42": ("M 42 (Orion Nebula)", 83.82208, -5.39111),
    "orion nebula": ("M 42 (Orion Nebula)", 83.82208, -5.39111),
    "ngc 1976": ("M 42 (Orion Nebula)", 83.82208, -5.39111),
}


class TargetResolver:
    """Resolve one target at a time; the network is used only after local lookup."""

    endpoint = "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?"

    def __init__(self, fetcher: Callable[[str, float], bytes] | None = None, timeout_seconds: float = 5.0) -> None:
        self.fetcher = fetcher or self._fetch
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def _fetch(url: str, timeout_seconds: float) -> bytes:
        with urlopen(url, timeout=timeout_seconds) as response:  # nosec B310: fixed CDS endpoint + quoted query
            return response.read(256_000)

    def resolve(self, raw_query: object) -> TargetResolution:
        if not isinstance(raw_query, str) or not (query := " ".join(raw_query.split())):
            return TargetResolution("INVALID_TARGET", "", message="Enter a target name or catalog identifier.")
        local = LOCAL_TARGETS.get(_key(query))
        if local:
            name, ra, dec = local
            return TargetResolution("RESOLVED_LOCAL", query, name, ra, dec, "Bundled local astronomical catalog", True)
        try:
            xml = self.fetcher(self.endpoint + quote(query, safe=""), self.timeout_seconds)
        except (TimeoutError, socket.timeout):
            return TargetResolution("RESOLVER_TIMEOUT", query, message="CDS Sesame did not respond before the resolver timeout.")
        except (HTTPError, URLError, OSError):
            return TargetResolution("RESOLVER_UNAVAILABLE", query, message="CDS Sesame is unavailable; try coordinates or a bundled target.")
        return self._parse_sesame(query, xml)

    @staticmethod
    def _parse_sesame(query: str, xml: bytes) -> TargetResolution:
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError:
            return TargetResolution("RESOLVER_UNAVAILABLE", query, message="CDS Sesame returned an unreadable response.")
        candidates = []
        for resolver in root.findall(".//Resolver"):
            try:
                ra = float((resolver.findtext("jradeg") or "").strip())
                dec = float((resolver.findtext("jdedeg") or "").strip())
            except ValueError:
                continue
            if math.isfinite(ra) and math.isfinite(dec) and 0 <= ra < 360 and -90 <= dec <= 90:
                candidates.append((resolver.findtext("oname") or resolver.findtext("name") or query, ra, dec, resolver.get("name") or "CDS Sesame"))
        if not candidates:
            return TargetResolution("UNKNOWN_TARGET", query, message="No coordinate-bearing CDS Sesame match was returned.")
        first = candidates[0]
        if any(abs(ra - first[1]) > .01 or abs(dec - first[2]) > .01 for _, ra, dec, _ in candidates[1:]):
            return TargetResolution("AMBIGUOUS_TARGET", query, message="CDS Sesame returned conflicting coordinate matches; refine the catalog identifier.")
        name, ra, dec, source = first
        return TargetResolution("RESOLVED_LIVE", query, " ".join(name.split()), ra, dec, f"CDS Sesame · {source}")
