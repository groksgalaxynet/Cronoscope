"""Single server-owned durable budget for the allowlisted product."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from research.dr1_cube_range.persistent_ledger import PersistentLedger

EXPERIMENT_ID = "CRONOSCOPE_DR1_6_SERVICE_NPIX7945_V1"
MAX_REQUESTS = 40
MAX_BYTES = 16 * 1024 * 1024


class BudgetController:
    """Open one fixed ledger; clients cannot create, reset, or resize it."""

    _initialization_lock = threading.Lock()

    def __init__(self, state_dir: Path | str) -> None:
        self.state_dir = Path(state_dir)
        self.ledger_path = self.state_dir / "archive_budget.sqlite3"
        with self._initialization_lock:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            if not self.ledger_path.exists():
                PersistentLedger.initialize(
                    self.ledger_path,
                    EXPERIMENT_ID,
                    max_requests=MAX_REQUESTS,
                    max_bytes=MAX_BYTES,
                )
        self.ledger = PersistentLedger(self.ledger_path, EXPERIMENT_ID)

    def public_snapshot(self) -> dict[str, Any]:
        snapshot = self.ledger.snapshot(include_requests=False)
        return {
            key: snapshot[key]
            for key in (
                "experiment_id", "max_requests", "max_bytes", "attempts",
                "actual_received_bytes", "charged_bytes", "remaining_requests",
                "remaining_charged_bytes", "accounting_semantics",
            )
        }
