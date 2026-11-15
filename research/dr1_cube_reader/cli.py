"""Command-line entry point for the experimental cube reader."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.dr1_cube_range.persistent_ledger import PersistentLedger
from research.dr1_cube_reader.reader import (
    CubeReader, HttpRangeSource, RegionRequest, SavedEvidenceSource, write_result,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--evidence-root", type=Path)
    mode.add_argument("--url")
    parser.add_argument("--expected-size", type=int)
    parser.add_argument("--ledger-db", type=Path)
    parser.add_argument("--experiment-id")
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--channel", required=True, type=int)
    parser.add_argument("--x", required=True, type=int)
    parser.add_argument("--y", required=True, type=int)
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    parser.add_argument("--allow-blank-channel", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.evidence_root is not None:
        source = SavedEvidenceSource(args.evidence_root)
    else:
        required = ("expected_size", "ledger_db", "experiment_id", "artifact_dir")
        missing = [name for name in required if getattr(args, name) is None]
        if missing:
            parser.error("live mode requires " + ", ".join(f"--{name.replace('_','-')}" for name in missing))
        ledger = PersistentLedger(args.ledger_db, args.experiment_id)
        print(json.dumps({"ledger_before_execution": ledger.snapshot()}, indent=2), flush=True)
        source = HttpRangeSource(
            args.url, ledger, args.artifact_dir, expected_size=args.expected_size
        )

    request = RegionRequest(
        args.channel, args.x, args.y, args.width, args.height,
        allow_blank_channel=args.allow_blank_channel,
    )
    result = CubeReader(source).open().read_region(request)
    saved_size = 0
    for _ in range(4):
        result["resources"]["saved_result_bytes"] = saved_size
        new_size = write_result(args.output, result)
        if new_size == saved_size:
            break
        saved_size = new_size
    else:  # pragma: no cover - integer digit growth converges immediately
        raise RuntimeError("saved result size did not converge")
    print(json.dumps({"output": str(args.output), "validation": result["validation"], "resources": result["resources"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
