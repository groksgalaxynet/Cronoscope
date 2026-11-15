from __future__ import annotations

import multiprocessing
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from research.dr1_cube_range.persistent_ledger import (
    LedgerStateError,
    PersistentBudgetExceeded,
    PersistentLedger,
)
from research.dr1_cube_range.range_cube import (
    BoundedRangeClient,
    ProductIdentity,
    RangeResponseError,
)


def _reserve_many(arguments: tuple[str, str, int]) -> int:
    path, experiment_id, count = arguments
    ledger = PersistentLedger(path, experiment_id)
    accepted = 0
    for index in range(count):
        try:
            ledger.reserve_request(
                method="GET", url=f"http://local/{os.getpid()}/{index}",
                planned_bytes=1, range_start=index, range_end=index,
            )
            accepted += 1
        except PersistentBudgetExceeded:
            pass
    return accepted


def _reserve_then_crash(path: str, experiment_id: str) -> None:
    ledger = PersistentLedger(path, experiment_id)
    ledger.reserve_request(
        method="GET", url="http://local/crash", planned_bytes=7,
        range_start=0, range_end=6,
    )
    os._exit(0)


class FixtureResponse:
    def __init__(self, status: int, body: bytes, headers: dict[str, str]) -> None:
        self.status_code = status
        self.body = body
        self.headers = headers
        self.url = "http://local/cube.fits"
        self.history: list[object] = []
        self.closed = False
        self.body_iterated = False

    def close(self) -> None:
        self.closed = True

    def iter_content(self, chunk_size: int):
        self.body_iterated = True
        if self.body:
            yield self.body


class FixtureSession:
    def __init__(self, response: FixtureResponse) -> None:
        self.response = response

    def get(self, *_args, **_kwargs):
        return self.response


class PersistentLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.db = Path(self.temporary.name) / "phase.sqlite3"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def initialize(self, *, requests: int = 20, bytes_: int = 100) -> PersistentLedger:
        return PersistentLedger.initialize(
            self.db, "offline-fixture", max_requests=requests, max_bytes=bytes_
        )

    def client(self, response: FixtureResponse, *, bytes_: int = 100):
        ledger = self.initialize(bytes_=bytes_)
        client = BoundedRangeClient(ledger, FixtureSession(response))
        client.identity = ProductIdentity(response.url, 100, None, None)
        return ledger, client

    def test_normal_bounded_request(self):
        response = FixtureResponse(
            206, b"x", {"Content-Range": "bytes 0-0/100", "Content-Length": "1"}
        )
        ledger, client = self.client(response)
        self.assertEqual(client.get(response.url, 0, 0), b"x")
        snapshot = ledger.snapshot()
        self.assertEqual((snapshot["attempts"], snapshot["actual_received_bytes"], snapshot["charged_bytes"]), (1, 1, 1))
        self.assertEqual(snapshot["requests"][0]["state"], "completed")

    def test_process_restart_preserves_budget(self):
        ledger = self.initialize(requests=2)
        ledger.reserve_request(method="GET", url="http://local/1", planned_bytes=1)
        restarted = PersistentLedger(self.db, "offline-fixture")
        restarted.reserve_request(method="GET", url="http://local/2", planned_bytes=1)
        with self.assertRaises(PersistentBudgetExceeded):
            PersistentLedger(self.db, "offline-fixture").reserve_request(
                method="GET", url="http://local/3", planned_bytes=1
            )

    def test_request_twenty_accepted_and_twenty_one_rejected(self):
        ledger = self.initialize(requests=20)
        for index in range(20):
            reservation = ledger.reserve_request(
                method="GET", url=f"http://local/{index}", planned_bytes=1
            )
            self.assertEqual(reservation.sequence, index + 1)
        with self.assertRaises(PersistentBudgetExceeded):
            ledger.reserve_request(method="GET", url="http://local/21", planned_bytes=1)

    def test_retry_is_a_distinct_attempt(self):
        ledger = self.initialize()
        first = ledger.reserve_request(method="GET", url="http://local/retry", planned_bytes=2)
        ledger.finish_request(first, state="failed", error="fixture")
        second = ledger.reserve_request(method="GET", url="http://local/retry", planned_bytes=2)
        self.assertEqual(second.sequence, 2)
        self.assertEqual(ledger.snapshot()["attempts"], 2)

    def test_interrupted_request_keeps_full_conservative_charge(self):
        ledger = self.initialize()
        reservation = ledger.reserve_request(method="GET", url="http://local/i", planned_bytes=10)
        ledger.record_received(reservation, 3)
        ledger.finish_request(reservation, state="interrupted", error="fixture disconnect")
        snapshot = ledger.snapshot()
        self.assertEqual(snapshot["actual_received_bytes"], 3)
        self.assertEqual(snapshot["charged_bytes"], 10)
        self.assertEqual(snapshot["requests"][0]["state"], "interrupted")

    def test_simulated_crash_after_reservation_remains_charged(self):
        self.initialize()
        process = multiprocessing.Process(
            target=_reserve_then_crash, args=(str(self.db), "offline-fixture")
        )
        process.start(); process.join(10)
        self.assertEqual(process.exitcode, 0)
        snapshot = PersistentLedger(self.db, "offline-fixture").snapshot()
        self.assertEqual((snapshot["attempts"], snapshot["charged_bytes"]), (1, 7))
        self.assertEqual(snapshot["requests"][0]["state"], "reserved")

    def test_concurrent_processes_cannot_exceed_shared_limit(self):
        self.initialize(requests=20, bytes_=1000)
        context = multiprocessing.get_context("fork")
        with context.Pool(6) as pool:
            accepted = pool.map(
                _reserve_many,
                [(str(self.db), "offline-fixture", 8)] * 6,
            )
        self.assertEqual(sum(accepted), 20)
        snapshot = PersistentLedger(self.db, "offline-fixture").snapshot()
        self.assertEqual(snapshot["attempts"], 20)
        self.assertEqual(len(snapshot["requests"]), 20)

    def test_missing_ledger_fails_closed(self):
        with self.assertRaises(LedgerStateError):
            PersistentLedger(self.db, "offline-fixture")

    def test_corrupt_ledger_fails_closed(self):
        self.db.write_bytes(b"not sqlite")
        with self.assertRaises(LedgerStateError):
            PersistentLedger(self.db, "offline-fixture")

    def test_semantically_inconsistent_ledger_fails_closed(self):
        self.initialize()
        connection = sqlite3.connect(self.db)
        connection.execute(
            "UPDATE experiments SET attempts=1 WHERE experiment_id='offline-fixture'"
        )
        connection.commit(); connection.close()
        with self.assertRaises(LedgerStateError):
            PersistentLedger(self.db, "offline-fixture")

    def test_truncated_response_counts_observed_and_charges_planned(self):
        response = FixtureResponse(
            206, b"x", {"Content-Range": "bytes 0-1/100", "Content-Length": "2"}
        )
        ledger, client = self.client(response)
        with self.assertRaisesRegex(RangeResponseError, "truncated"):
            client.get(response.url, 0, 1)
        snapshot = ledger.snapshot()
        self.assertEqual((snapshot["actual_received_bytes"], snapshot["charged_bytes"]), (1, 2))
        self.assertEqual(snapshot["requests"][0]["state"], "failed")

    def test_http_200_is_rejected_without_reading_body(self):
        response = FixtureResponse(200, b"entire product", {"Content-Length": "14"})
        ledger, client = self.client(response)
        with self.assertRaisesRegex(RangeResponseError, "body was not consumed"):
            client.get(response.url, 0, 0)
        self.assertFalse(response.body_iterated)
        self.assertEqual(ledger.snapshot()["actual_received_bytes"], 0)

    def test_incorrect_content_range_is_rejected(self):
        response = FixtureResponse(
            206, b"x", {"Content-Range": "bytes 1-1/100", "Content-Length": "1"}
        )
        ledger, client = self.client(response)
        with self.assertRaises(RangeResponseError):
            client.get(response.url, 0, 0)
        self.assertEqual(ledger.snapshot()["actual_received_bytes"], 0)

    def test_excessive_actual_body_is_recorded_conservatively(self):
        response = FixtureResponse(
            206, b"xx", {"Content-Range": "bytes 0-0/100", "Content-Length": "1"}
        )
        ledger, client = self.client(response)
        with self.assertRaises(PersistentBudgetExceeded):
            client.get(response.url, 0, 0)
        snapshot = ledger.snapshot()
        self.assertEqual((snapshot["actual_received_bytes"], snapshot["charged_bytes"]), (2, 2))
        self.assertEqual(snapshot["requests"][0]["state"], "failed")

    def test_transfer_budget_exhaustion_prevents_attempt(self):
        ledger = self.initialize(bytes_=3)
        ledger.reserve_request(method="GET", url="http://local/a", planned_bytes=3)
        with self.assertRaises(PersistentBudgetExceeded):
            ledger.reserve_request(method="GET", url="http://local/b", planned_bytes=1)
        self.assertEqual(ledger.snapshot()["attempts"], 1)

    def test_same_experiment_id_cannot_be_reinitialized(self):
        ledger = self.initialize()
        ledger.reserve_request(method="GET", url="http://local/a", planned_bytes=1)
        before = ledger.snapshot(include_requests=False)
        with self.assertRaises(LedgerStateError):
            PersistentLedger.initialize(
                self.db, "offline-fixture", max_requests=20, max_bytes=100
            )
        after = PersistentLedger(self.db, "offline-fixture").snapshot(include_requests=False)
        self.assertEqual(before, after)

    def test_new_experiment_id_requires_explicit_initialization(self):
        self.initialize()
        with self.assertRaises(LedgerStateError):
            PersistentLedger(self.db, "new-id")
        created = PersistentLedger.initialize(
            self.db, "new-id", max_requests=2, max_bytes=10
        )
        self.assertEqual(created.snapshot()["remaining_requests"], 2)

    def test_failed_initialization_preserves_corrupt_file(self):
        original = b"irreplaceable prior evidence"
        self.db.write_bytes(original)
        with self.assertRaises(LedgerStateError):
            PersistentLedger.initialize(
                self.db, "offline-fixture", max_requests=20, max_bytes=100
            )
        self.assertEqual(self.db.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
