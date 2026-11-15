"""Structured, browser-safe service failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ServiceError(RuntimeError):
    code: str
    message: str
    http_status: int = 400
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        RuntimeError.__init__(self, self.message)

    def envelope(self) -> dict[str, Any]:
        return {
            "classification": "EXPERIMENTAL_DR1_CUBE_SAMPLE_ERROR",
            "status": "ERROR",
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }
