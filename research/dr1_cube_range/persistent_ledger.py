"""Durable, process-safe accounting for bounded HTTP research experiments.

The budget charge for a response is committed before the network request.  A
completed response therefore charges exactly its declared maximum.  A failed,
interrupted, or crashed response keeps that full conservative charge even when
fewer bytes were observed.  This can overcount, but cannot allow a restart or
an unrecorded final chunk to undercount the safety budget.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"


class LedgerError(RuntimeError):
    """Base error for persistent accounting."""


class LedgerStateError(LedgerError):
    """The ledger is absent, corrupt, incompatible, or not initialized."""


class PersistentBudgetExceeded(LedgerError):
    """A request cannot be reserved within the shared phase budget."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class Reservation:
    request_id: int
    experiment_id: str
    sequence: int
    planned_bytes: int


class PersistentLedger:
    """SQLite-backed phase ledger with pre-request durable reservations."""

    def __init__(self, path: Path | str, experiment_id: str) -> None:
        self.path = Path(path)
        self.experiment_id = experiment_id
        if not experiment_id or experiment_id.strip() != experiment_id:
            raise LedgerStateError("experiment ID must be explicit and non-blank")
        if not self.path.is_file():
            raise LedgerStateError(f"ledger does not exist: {self.path}")
        self._validate()

    @classmethod
    def initialize(
        cls,
        path: Path | str,
        experiment_id: str,
        *,
        max_requests: int,
        max_bytes: int,
    ) -> "PersistentLedger":
        path = Path(path)
        if not experiment_id or experiment_id.strip() != experiment_id:
            raise LedgerStateError("experiment ID must be explicit and non-blank")
        if max_requests <= 0 or max_bytes <= 0:
            raise LedgerStateError("budgets must be positive")
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        try:
            connection = cls._connect(path, create=True)
            try:
                cls._ensure_schema(connection)
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO experiments(
                        experiment_id, max_requests, max_bytes, attempts,
                        actual_received_bytes, charged_bytes, created_at
                    ) VALUES (?, ?, ?, 0, 0, 0, ?)
                    """,
                    (experiment_id, max_requests, max_bytes, _utc_now()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except (sqlite3.DatabaseError, sqlite3.IntegrityError) as exc:
            # Never replace or recreate an existing unreadable ledger.
            raise LedgerStateError(
                f"ledger initialization failed; prior file preserved={existed}: {exc}"
            ) from exc
        return cls(path, experiment_id)

    @staticmethod
    def _connect(path: Path, *, create: bool = False) -> sqlite3.Connection:
        if create:
            connection = sqlite3.connect(path, timeout=10.0, isolation_level=None)
        else:
            uri = f"file:{path.resolve()}?mode=rw"
            connection = sqlite3.connect(uri, uri=True, timeout=10.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiments(
                experiment_id TEXT PRIMARY KEY,
                max_requests INTEGER NOT NULL CHECK(max_requests > 0),
                max_bytes INTEGER NOT NULL CHECK(max_bytes > 0),
                attempts INTEGER NOT NULL CHECK(attempts >= 0),
                actual_received_bytes INTEGER NOT NULL CHECK(actual_received_bytes >= 0),
                charged_bytes INTEGER NOT NULL CHECK(charged_bytes >= 0),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS requests(
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
                sequence INTEGER NOT NULL,
                method TEXT NOT NULL,
                url TEXT NOT NULL,
                range_start INTEGER,
                range_end INTEGER,
                planned_bytes INTEGER NOT NULL CHECK(planned_bytes >= 0),
                actual_received_bytes INTEGER NOT NULL DEFAULT 0 CHECK(actual_received_bytes >= 0),
                state TEXT NOT NULL,
                pid INTEGER NOT NULL,
                reserved_at TEXT NOT NULL,
                finished_at TEXT,
                http_status INTEGER,
                content_range TEXT,
                error TEXT,
                UNIQUE(experiment_id, sequence)
            );
            """
        )
        current = connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        if current is None:
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES('schema_version', ?)",
                (SCHEMA_VERSION,),
            )
        elif current["value"] != SCHEMA_VERSION:
            raise LedgerStateError("unsupported ledger schema version")

    def _validate(self) -> None:
        try:
            connection = self._connect(self.path)
            try:
                check = connection.execute("PRAGMA quick_check").fetchone()
                if check is None or check[0] != "ok":
                    raise LedgerStateError("ledger integrity check failed")
                version = connection.execute(
                    "SELECT value FROM metadata WHERE key='schema_version'"
                ).fetchone()
                if version is None or version["value"] != SCHEMA_VERSION:
                    raise LedgerStateError("missing or unsupported ledger schema")
                row = connection.execute(
                    "SELECT * FROM experiments WHERE experiment_id=?",
                    (self.experiment_id,),
                ).fetchone()
                if row is None:
                    raise LedgerStateError(
                        "experiment ID is not initialized; explicit initialization required"
                    )
                totals = connection.execute(
                    """
                    SELECT COUNT(*) AS attempts,
                           COALESCE(SUM(actual_received_bytes), 0) AS actual_bytes,
                           COALESCE(SUM(
                               CASE WHEN actual_received_bytes > planned_bytes
                                    THEN actual_received_bytes ELSE planned_bytes END
                           ), 0) AS charged_bytes,
                           COALESCE(SUM(
                               CASE WHEN state IN
                                   ('reserved','completed','failed','interrupted','rejected')
                                    THEN 0 ELSE 1 END
                           ), 0) AS invalid_states
                    FROM requests WHERE experiment_id=?
                    """,
                    (self.experiment_id,),
                ).fetchone()
                if (
                    row["attempts"] != totals["attempts"]
                    or row["actual_received_bytes"] != totals["actual_bytes"]
                    or row["charged_bytes"] != totals["charged_bytes"]
                    or totals["invalid_states"] != 0
                    or row["attempts"] > row["max_requests"]
                ):
                    raise LedgerStateError("ledger counters or request states are inconsistent")
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise LedgerStateError(f"ledger is corrupt or unreadable: {exc}") from exc

    def reserve_request(
        self,
        *,
        method: str,
        url: str,
        planned_bytes: int,
        range_start: int | None = None,
        range_end: int | None = None,
    ) -> Reservation:
        """Commit the attempt and conservative byte charge before network I/O."""
        if planned_bytes < 0:
            raise ValueError("planned bytes cannot be negative")
        try:
            connection = self._connect(self.path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM experiments WHERE experiment_id=?",
                    (self.experiment_id,),
                ).fetchone()
                if row is None:
                    raise LedgerStateError("experiment ledger disappeared")
                if row["attempts"] >= row["max_requests"]:
                    raise PersistentBudgetExceeded("request-attempt limit reached")
                if row["charged_bytes"] + planned_bytes > row["max_bytes"]:
                    raise PersistentBudgetExceeded("response-body budget would be exceeded")
                sequence = int(row["attempts"]) + 1
                cursor = connection.execute(
                    """
                    INSERT INTO requests(
                        experiment_id, sequence, method, url, range_start,
                        range_end, planned_bytes, state, pid, reserved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'reserved', ?, ?)
                    """,
                    (
                        self.experiment_id, sequence, method, url, range_start,
                        range_end, planned_bytes, os.getpid(), _utc_now(),
                    ),
                )
                connection.execute(
                    """
                    UPDATE experiments
                    SET attempts=attempts+1, charged_bytes=charged_bytes+?
                    WHERE experiment_id=?
                    """,
                    (planned_bytes, self.experiment_id),
                )
                connection.commit()
                return Reservation(
                    int(cursor.lastrowid), self.experiment_id, sequence, planned_bytes
                )
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise LedgerStateError(f"ledger reservation failed closed: {exc}") from exc

    def record_received(self, reservation: Reservation, byte_count: int) -> None:
        if byte_count < 0:
            raise ValueError("received byte count cannot be negative")
        if byte_count == 0:
            return
        try:
            connection = self._connect(self.path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT * FROM requests WHERE request_id=? AND experiment_id=?",
                    (reservation.request_id, self.experiment_id),
                ).fetchone()
                if row is None:
                    raise LedgerStateError("request reservation is missing")
                new_total = int(row["actual_received_bytes"]) + byte_count
                previous_overage = max(
                    0, int(row["actual_received_bytes"]) - int(row["planned_bytes"])
                )
                new_overage = max(0, new_total - int(row["planned_bytes"]))
                connection.execute(
                    "UPDATE requests SET actual_received_bytes=? WHERE request_id=?",
                    (new_total, reservation.request_id),
                )
                connection.execute(
                    """
                    UPDATE experiments
                    SET actual_received_bytes=actual_received_bytes+?,
                        charged_bytes=charged_bytes+?
                    WHERE experiment_id=?
                    """,
                    (
                        byte_count, new_overage - previous_overage,
                        self.experiment_id,
                    ),
                )
                connection.commit()
                if new_total > int(row["planned_bytes"]):
                    raise PersistentBudgetExceeded(
                        "response exceeded its precharged maximum length"
                    )
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise LedgerStateError(f"received-byte update failed closed: {exc}") from exc

    def finish_request(
        self,
        reservation: Reservation,
        *,
        state: str,
        http_status: int | None = None,
        content_range: str | None = None,
        error: str | None = None,
    ) -> None:
        if state not in {"completed", "failed", "interrupted", "rejected"}:
            raise ValueError("invalid terminal request state")
        try:
            connection = self._connect(self.path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                updated = connection.execute(
                    """
                    UPDATE requests
                    SET state=?, finished_at=?, http_status=?, content_range=?, error=?
                    WHERE request_id=? AND experiment_id=? AND state='reserved'
                    """,
                    (
                        state, _utc_now(), http_status, content_range, error,
                        reservation.request_id, self.experiment_id,
                    ),
                ).rowcount
                if updated != 1:
                    raise LedgerStateError("request is missing or already finalized")
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()
        except sqlite3.DatabaseError as exc:
            raise LedgerStateError(f"request finalization failed closed: {exc}") from exc

    def snapshot(self, *, include_requests: bool = True) -> dict[str, Any]:
        self._validate()
        connection = self._connect(self.path)
        try:
            row = connection.execute(
                "SELECT * FROM experiments WHERE experiment_id=?",
                (self.experiment_id,),
            ).fetchone()
            if row is None:
                raise LedgerStateError("experiment ledger disappeared")
            result: dict[str, Any] = dict(row)
            result["remaining_requests"] = row["max_requests"] - row["attempts"]
            result["remaining_charged_bytes"] = row["max_bytes"] - row["charged_bytes"]
            result["accounting_semantics"] = (
                "actual_received_bytes records committed observed chunks; charged_bytes "
                "reserves the full planned body before I/O and is never refunded"
            )
            if include_requests:
                result["requests"] = [
                    dict(item)
                    for item in connection.execute(
                        "SELECT * FROM requests WHERE experiment_id=? ORDER BY sequence",
                        (self.experiment_id,),
                    ).fetchall()
                ]
            return result
        finally:
            connection.close()
