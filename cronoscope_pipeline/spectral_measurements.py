"""Import and publish genuine SPHEREx forced-photometry measurements.

This module deliberately consumes exported extraction results; it does not
submit jobs to IRSA or derive spectra from Level-2 image pixels.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import astropy.units as u
from astropy.table import Table


class SpectrumStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING_SPECTRAL_DATA"
    INVALID = "INVALID_SPECTRAL_DATA"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_EXTRACTION_FORMAT"


@dataclass(frozen=True)
class SpectralMeasurement:
    target_id: str
    observation_id: str | None
    observation_mjd: float | None
    wavelength_um: float | None
    wavelength_source_value: float | None
    wavelength_source_unit: str | None
    flux_density: float | None
    flux_unit: str | None
    flux_uncertainty: float | None
    flux_uncertainty_unit: str | None
    wavelength_width_um: float | None
    quality_flags: int | None
    fit_quality: float | None
    detector: str | None
    processing_release: str | None
    source_provenance: str
    extraction_method: str
    usable: bool
    unusable_reason: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportedSpectrum:
    spectrum_id: str
    target_id: str
    status: SpectrumStatus
    measurements: tuple[SpectralMeasurement, ...]
    source_format: str | None
    source_provenance: str
    extraction_method: str
    warning: str | None = None

    def to_jsonable(self) -> dict[str, Any]:
        return {"schema_version": "cronoscope-spectral-v1", "spectrum_id": self.spectrum_id,
                "target_id": self.target_id, "status": self.status.value,
                "source_format": self.source_format, "source_provenance": self.source_provenance,
                "extraction_method": self.extraction_method, "warning": self.warning,
                "measurements": [item.to_jsonable() for item in self.measurements]}


_COLUMNS = {
    "wavelength": ("wavelength", "lambda"), "flux": ("flux",), "flux_err": ("flux_err", "flux_error"),
    "lambda_width": ("lambda_width", "wavelength_width"), "flags": ("flags", "flag"),
    "fit_ql": ("fit_ql", "fit_quality"), "mjd": ("mjd",), "detector": ("det_id", "detector"),
    "lvf_id": ("lvf_id", "observation_id"), "data_collection": ("data_collection", "processing_release"),
}


def _column(table: Table, key: str):
    names = {name.casefold(): name for name in table.colnames}
    return next((table[names[name]] for name in _COLUMNS[key] if name in names), None)


def _value(column: Any, index: int) -> float | None:
    if column is None or np.ma.is_masked(column[index]):
        return None
    try:
        value = float(column[index])
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def _text(column: Any, index: int) -> str | None:
    if column is None or np.ma.is_masked(column[index]):
        return None
    value = str(column[index]).strip()
    return value or None


def _wavelength_um(column: Any, index: int) -> float | None:
    value = _value(column, index)
    if value is None:
        return None
    try:
        unit = u.Unit(column.unit) if getattr(column, "unit", None) else u.um
        return float((value * unit).to_value(u.um))
    except (u.UnitConversionError, ValueError, TypeError):
        return None


def import_spectrophotometry(path: str | Path, *, spectrum_id: str | None = None,
                             target_id: str | None = None, source_provenance: str | None = None) -> ImportedSpectrum:
    """Read an official IRSA Spectrophotometry Tool VOTable without altering values."""
    source = Path(path)
    identifier, target = spectrum_id or source.stem, target_id or source.stem
    provenance = source_provenance or "IRSA SPHEREx Spectrophotometry Tool exported VOTable"
    method = "IRSA Spectrophotometry Tool forced photometry import"
    if source.suffix.casefold() not in {".vot", ".xml"}:
        return ImportedSpectrum(identifier, target, SpectrumStatus.UNSUPPORTED_FORMAT, (), source.suffix or None,
                                provenance, method, "Only VOTable/XML Spectrophotometry Tool exports are supported.")
    try:
        table = Table.read(source, format="votable")
    except Exception as exc:
        return ImportedSpectrum(identifier, target, SpectrumStatus.INVALID, (), "VOTable", provenance, method,
                                f"Could not read VOTable: {exc}")
    wavelength, flux = _column(table, "wavelength"), _column(table, "flux")
    if wavelength is None or flux is None:
        return ImportedSpectrum(identifier, target, SpectrumStatus.INVALID, (), "VOTable", provenance, method,
                                "VOTable requires wavelength and flux columns.")
    optional = {name: _column(table, name) for name in _COLUMNS if name not in {"wavelength", "flux"}}
    rows: list[SpectralMeasurement] = []
    for index in range(len(table)):
        wavelength_value, wavelength_um, flux_value = _value(wavelength, index), _wavelength_um(wavelength, index), _value(flux, index)
        usable = wavelength_um is not None and flux_value is not None
        reason = None if usable else "Missing, non-finite, or unit-incompatible wavelength/flux value."
        flags = _value(optional["flags"], index)
        rows.append(SpectralMeasurement(
            target, _text(optional["lvf_id"], index), _value(optional["mjd"], index), wavelength_um,
            wavelength_value, str(getattr(wavelength, "unit", None) or "um"), flux_value,
            str(getattr(flux, "unit", None) or "unknown"), _value(optional["flux_err"], index),
            str(getattr(optional["flux_err"], "unit", None) or getattr(flux, "unit", None) or "unknown"),
            _wavelength_um(optional["lambda_width"], index), None if flags is None else int(flags),
            _value(optional["fit_ql"], index), _text(optional["detector"], index),
            _text(optional["data_collection"], index), provenance, method, usable, reason))
    status = SpectrumStatus.AVAILABLE if any(row.usable for row in rows) else SpectrumStatus.INVALID
    warning = None if status is SpectrumStatus.AVAILABLE else "No usable wavelength/flux measurements were present."
    return ImportedSpectrum(identifier, target, status, tuple(rows), "VOTable", provenance, method, warning)


class SpectralRepository:
    """Small read-only registry for owner-supplied official extraction files."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def get(self, spectrum_id: str) -> ImportedSpectrum:
        for suffix in (".vot", ".xml"):
            candidate = self.directory / f"{spectrum_id}{suffix}"
            if candidate.is_file():
                return import_spectrophotometry(candidate, spectrum_id=spectrum_id)
        return ImportedSpectrum(spectrum_id, spectrum_id, SpectrumStatus.MISSING, (), None,
                                "No owner-supplied IRSA extraction file is present.",
                                "IRSA Spectrophotometry Tool forced photometry import",
                                "Place an official VOTable at spectral_measurements/<spectrum_id>.vot.")


def export_static_spectrum(spectrum: ImportedSpectrum, destination: str | Path) -> None:
    """Write the browser payload without changing source measurements or FITS products."""
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spectrum.to_jsonable(), allow_nan=False, separators=(",", ":")), encoding="utf-8")
