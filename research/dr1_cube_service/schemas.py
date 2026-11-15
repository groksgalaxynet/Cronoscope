"""Strict request parsing for the experimental cube endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ServiceError

EXPECTED_FIELDS = frozenset({"product_id", "channel", "x", "y", "width", "height"})
BLANK_CHANNELS = frozenset({51, 52})


def _strict_integer(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ServiceError("INVALID_REQUEST", f"{key} must be an integer")
    return value


@dataclass(frozen=True)
class SampleRequest:
    product_id: str
    channel: int
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def parse(cls, payload: object) -> "SampleRequest":
        if not isinstance(payload, dict):
            raise ServiceError("INVALID_REQUEST", "JSON request body must be an object")
        fields = frozenset(payload)
        unknown = sorted(fields - EXPECTED_FIELDS)
        missing = sorted(EXPECTED_FIELDS - fields)
        if unknown:
            raise ServiceError(
                "UNKNOWN_PARAMETERS", "Unknown request parameters are not allowed.",
                details={"parameters": unknown},
            )
        if missing:
            raise ServiceError(
                "MISSING_PARAMETERS", "Required request parameters are missing.",
                details={"parameters": missing},
            )
        product_id = payload["product_id"]
        if not isinstance(product_id, str):
            raise ServiceError("INVALID_PRODUCT_ID", "product_id must be a string")
        values = {key: _strict_integer(payload, key) for key in ("channel", "x", "y", "width", "height")}
        channel = values["channel"]
        if not 0 <= channel <= 101:
            raise ServiceError("INVALID_CHANNEL", "channel must be in the inclusive range 0..101")
        if channel in BLANK_CHANNELS:
            raise ServiceError(
                "MISSING_CHANNEL", f"channel {channel} is intentionally blank and unavailable for ordinary sampling"
            )
        width, height = values["width"], values["height"]
        if width <= 0 or height <= 0:
            raise ServiceError("INVALID_REGION", "width and height must be positive")
        if width > 32 or height > 32:
            raise ServiceError("REGION_TOO_LARGE", "region dimensions cannot exceed 32x32")
        x, y = values["x"], values["y"]
        if x < 0 or y < 0 or x + width > 512 or y + height > 512:
            raise ServiceError("REGION_OUT_OF_BOUNDS", "region must be contained within the 512x512 cube tile")
        return cls(product_id, channel, x, y, width, height)
