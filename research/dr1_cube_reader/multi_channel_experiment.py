"""Controlled DR1.5 multi-channel experiment runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import time
from pathlib import Path
from typing import Any

import numpy as np
from astropy.io import fits

from research.dr1_cube_range.persistent_ledger import PersistentLedger
from research.dr1_cube_range.range_cube import write_sparse_equivalent
from research.dr1_cube_reader.reader import CubeReader, HttpRangeSource, RegionRequest

CHANNELS = (0, 20, 100)
REGIONS = ((90, 107, 4, 4), (94, 107, 4, 4))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def _array(value: Any, dtype: str) -> np.ndarray:
    if dtype.startswith(">f"):
        return np.asarray(
            [[np.nan if item is None else item for item in row] for row in value],
            dtype=float,
        )
    return np.asarray(value)


def _sha256_file(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(
    *, url: str, expected_size: int, ledger_path: Path, experiment_id: str,
    artifact_dir: Path, output_path: Path, sparse_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    ledger = PersistentLedger(ledger_path, experiment_id)
    before = ledger.snapshot()
    if before["attempts"] != 0:
        raise RuntimeError("live experiment requires a fresh zero-attempt ledger")
    source = HttpRangeSource(
        url, ledger, artifact_dir / "responses", expected_size=expected_size
    )
    reader = CubeReader(source, header_output_dir=artifact_dir / "headers").open()
    samples: list[dict[str, Any]] = []
    for channel in CHANNELS:
        for region_index, (x, y, width, height) in enumerate(REGIONS, start=1):
            result = reader.read_region(RegionRequest(channel, x, y, width, height))
            sample = {"region_index": region_index, **result}
            samples.append(sample)
            _write_json(output_path, {
                "classification": "IN_PROGRESS",
                "experiment_id": experiment_id,
                "planned_channels": list(CHANNELS),
                "planned_regions": [list(item) for item in REGIONS],
                "samples": samples,
                "ledger": ledger.snapshot(),
            })

    # Stop network access here. Everything below uses only persisted bytes.
    ranges: list[tuple[int, bytes]] = []
    for metadata_path in sorted((artifact_dir / "responses").glob("request_*_bytes_*.json")):
        metadata = json.loads(metadata_path.read_text())
        ranges.append((metadata["start"], metadata_path.with_suffix(".bin").read_bytes()))
    write_sparse_equivalent(
        sparse_path, source.identity.content_length, reader.layouts or [], ranges
    )
    comparisons: list[dict[str, Any]] = []
    with fits.open(sparse_path, memmap=True, lazy_load_hdus=True) as hdul:
        for sample in samples:
            request = sample["request"]
            channel=request["channel_zero_based"]; x=request["x"]; y=request["y"]
            width=request["width"]; height=request["height"]
            matches = {}
            for name in ("IMAGE", "NHITS", "FLAGS"):
                independent=np.asarray(hdul[name].data[channel,y:y+height,x:x+width])
                standalone=_array(sample["arrays"][name]["values"],sample["arrays"][name]["dtype"])
                matches[name]=bool(np.array_equal(independent,standalone,equal_nan=True))
            comparisons.append({
                "channel": channel, "region_index": sample["region_index"],
                "matches": matches, "all_match": all(matches.values()),
            })
        image_unit=hdul["IMAGE"].header.get("BUNIT")
    if not all(item["all_match"] for item in comparisons):
        raise RuntimeError("independent Astropy validation disagreed")

    final_ledger=ledger.snapshot()
    sparse_digest=_sha256_file(sparse_path)
    result = {
        "schema_version": 1,
        "classification": "MULTI_CHANNEL_INDEPENDENT_DECODER_MATCH",
        "experiment_id": experiment_id,
        "product_identity": vars(source.identity),
        "channels": list(CHANNELS),
        "regions": [list(item) for item in REGIONS],
        "samples": samples,
        "independent_validation": {
            "method": "Astropy sparse logical FITS read of the same genuine persisted ranges",
            "comparisons": comparisons,
            "image_unit": image_unit,
            "external_photometric_calibration": False,
        },
        "ledger": final_ledger,
        "resource": {
            "runtime_seconds": time.perf_counter()-started,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "sparse_logical_bytes": sparse_path.stat().st_size,
            "sparse_allocated_bytes": sparse_path.stat().st_blocks*512,
        },
        "artifact_sha256": {
            "sparse_validation_fits": sparse_digest,
        },
        "limitations": [
            "Independent decoding is not independent photometric calibration.",
            "Cube pixels are coadded surface brightness, not observation epochs.",
            "NHITS is not uncertainty and FLAGS remain raw integers.",
        ],
    }
    _write_json(output_path,result)
    return result


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",required=True)
    parser.add_argument("--expected-size",required=True,type=int)
    parser.add_argument("--ledger-db",required=True,type=Path)
    parser.add_argument("--experiment-id",required=True)
    parser.add_argument("--artifact-dir",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--sparse",required=True,type=Path)
    args=parser.parse_args()
    result=run(
        url=args.url,expected_size=args.expected_size,ledger_path=args.ledger_db,
        experiment_id=args.experiment_id,artifact_dir=args.artifact_dir,
        output_path=args.output,sparse_path=args.sparse,
    )
    print(json.dumps({
        "classification":result["classification"],
        "attempts":result["ledger"]["attempts"],
        "body_bytes":result["ledger"]["actual_received_bytes"],
        "resource":result["resource"],
    },indent=2))
    return 0


if __name__=="__main__": raise SystemExit(main())
