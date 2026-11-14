"""Deterministic observation-to-epoch grouping with no inferred spectral map."""

from __future__ import annotations

from collections import defaultdict

from .models import EpochGroup, ObservationRecord, SkyAreaGroup


def _band_sort_key(record: ObservationRecord) -> tuple[float, str]:
    return (float("inf") if record.wavelength_min_m is None else record.wavelength_min_m, record.band_label or "")


def group_observations(records: list[ObservationRecord], *, area_key: str) -> SkyAreaGroup:
    """Group records by native ``obs_id`` and expose their actual band metadata.

    The supplied area key identifies the caller's query/target bucket. Exact
    same-footprint verification deliberately belongs to Pipeline 5.
    """
    by_observation: dict[str, list[ObservationRecord]] = defaultdict(list)
    for index, record in enumerate(records):
        by_observation[record.observation_id or f"UNKNOWN_OBSERVATION_{index:06d}"].append(record)

    epochs = []
    for observation_id, members in by_observation.items():
        members.sort(key=_band_sort_key)
        starts = [item.t_min_mjd for item in members if item.t_min_mjd is not None]
        ends = [item.t_max_mjd for item in members if item.t_max_mjd is not None]
        epochs.append(EpochGroup(
            observation_id=observation_id,
            start_mjd=min(starts) if starts else None,
            end_mjd=max(ends) if ends else None,
            bands=tuple(members),
        ))
    epochs.sort(key=lambda epoch: (float("inf") if epoch.start_mjd is None else epoch.start_mjd, epoch.observation_id))
    return SkyAreaGroup(
        area_key=area_key,
        epochs=tuple(epochs),
        warnings=(
            "Epochs are grouped by native obs_id and actual archive times; no six-month cadence is assumed.",
            "Band labels and wavelength bounds are archive metadata. This representation does not map products to 102 mission bands.",
            "This is a query/metadata grouping, not exact image-footprint containment.",
        ),
    )
