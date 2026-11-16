from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from research.dr1_cube_range.persistent_ledger import PersistentBudgetExceeded
from research.dr1_cube_service.cache import RangeCache
from research.dr1_cube_service.errors import ServiceError
from research.dr1_cube_service.resolver import NPIX7945, ProductResolver
from research.dr1_cube_service.service import (
    CubeSampleService,
    GenuineEvidenceSource,
    LiveAllowlistedSource,
    NoRedirectAllowlistedSession,
    ServiceConfig,
)
from research.dr1_cube_range.range_cube import ProductIdentity

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    ROOT / "research" / "dr1_cube_reader" / "evidence" /
    "CRONOSCOPE_DR1_5_NPIX7945_MULTI_2026_11_15"
)
PUBLIC_FIXTURE = ROOT / "research" / "dr1_cube_service" / "fixtures" / "Npix7945_verified_samples.json"


class RedirectResponse:
    status_code = 302

    def close(self) -> None:
        pass


class RedirectSession:
    def head(self, *_args, **_kwargs):
        return RedirectResponse()

    def get(self, *_args, **_kwargs):
        return RedirectResponse()


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state = Path(self.temporary.name)
        self.service = CubeSampleService(ServiceConfig(self.state))
        self.reference = json.loads(PUBLIC_FIXTURE.read_text())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def payload(channel=20, x=90, y=107, width=4, height=4):
        return {
            "product_id": "Npix7945_cube", "channel": channel,
            "x": x, "y": y, "width": width, "height": height,
        }

    def test_all_six_preserved_samples_match_genuine_arrays_and_metadata(self) -> None:
        expected = {
            (
                sample["request"]["channel_zero_based"], sample["request"]["x"],
                sample["request"]["y"], sample["request"]["width"],
                sample["request"]["height"],
            ): sample
            for sample in self.reference["samples"]
        }
        for channel in (0, 20, 100):
            for x in (90, 94):
                with self.subTest(channel=channel, x=x):
                    result = self.service.sample(self.payload(channel, x=x))
                    sample = expected[(channel, x, 107, 4, 4)]
                    self.assertEqual(result["classification"], "EXPERIMENTAL_DR1_CUBE_SAMPLE")
                    self.assertTrue(result["validation"]["genuine_evidence_match"])
                    self.assertTrue(result["validation"]["public_result_replay"])
                    self.assertEqual(
                        result["validation"]["genuine_evidence_match_basis"],
                        "recorded_in_verified_source_result",
                    )
                    self.assertEqual(result["wavelength_metadata"], sample["science"]["channel"])
                    for name in ("IMAGE", "NHITS", "FLAGS"):
                        self.assertEqual(result["arrays"][name]["values"], sample["arrays"][name]["values"])
                    self.assertEqual(result["product"]["official_url"], NPIX7945.url)
                    self.assertEqual(result["science"]["image_unit"], "MJy/sr")
                    self.assertEqual(result["resources"]["external_requests_this_call"], 0)
                    self.assertEqual(result["resources"]["external_bytes_this_call"], 0)

    def test_strict_request_validation_and_no_arbitrary_url(self) -> None:
        failures = [
            (self.payload(channel=-1), "INVALID_CHANNEL"),
            (self.payload(channel=102), "INVALID_CHANNEL"),
            (self.payload(channel=51), "MISSING_CHANNEL"),
            (self.payload(channel=52), "MISSING_CHANNEL"),
            (self.payload(width=33), "REGION_TOO_LARGE"),
            (self.payload(width=0), "INVALID_REGION"),
            (self.payload(x=510, width=4), "REGION_OUT_OF_BOUNDS"),
            ({**self.payload(), "channel": True}, "INVALID_REQUEST"),
            ({**self.payload(), "product_id": "unknown"}, "UNKNOWN_PRODUCT"),
            ({**self.payload(), "url": "http://127.0.0.1/private"}, "UNKNOWN_PARAMETERS"),
            ({**self.payload(), "path": "/etc/passwd"}, "UNKNOWN_PARAMETERS"),
        ]
        for payload, code in failures:
            with self.subTest(code=code), self.assertRaises(ServiceError) as caught:
                self.service.sample(payload)
            self.assertEqual(caught.exception.code, code)

    def test_valid_but_unpreserved_sample_reports_missing_evidence(self) -> None:
        with self.assertRaises(ServiceError) as caught:
            self.service.sample(self.payload(channel=1))
        self.assertEqual(caught.exception.code, "GENUINE_EVIDENCE_UNAVAILABLE")
        self.assertIn("no value was fabricated", caught.exception.message)

    def test_missing_public_fixture_reports_unavailable_instead_of_crashing(self) -> None:
        service = CubeSampleService(ServiceConfig(
            self.state / "missing", public_result_fixture=self.state / "absent.json"
        ))
        with self.assertRaises(ServiceError) as caught:
            service.sample(self.payload())
        self.assertEqual(caught.exception.code, "GENUINE_EVIDENCE_UNAVAILABLE")
        self.assertIn("no value was fabricated", caught.exception.message)

    def test_cache_corruption_is_detected_then_refetched_from_evidence(self) -> None:
        if not (EVIDENCE / "multi_channel_result.json").is_file():
            self.skipTest("private raw-range evidence is not included in public checkouts")
        self.service = CubeSampleService(ServiceConfig(self.state, EVIDENCE))
        first = self.service.sample(self.payload())
        self.assertTrue(first["validation"]["genuine_evidence_match"])
        cached = next((self.state / "range_cache").glob("*.bin"))
        cached.write_bytes(b"corrupt")
        second = self.service.sample(self.payload())
        self.assertTrue(second["validation"]["genuine_evidence_match"])
        self.assertGreaterEqual(second["resources"]["cache"]["corruptions"], 1)

    def test_interrupted_cache_file_is_not_served(self) -> None:
        cache_root = self.state / "interrupted"
        cache_root.mkdir()
        stale = cache_root / "partial.bin.123.tmp"
        stale.write_bytes(b"partial")
        RangeCache(cache_root)
        self.assertFalse(stale.exists())

    def test_cache_is_bounded_and_evicts_least_recently_used_ranges(self) -> None:
        cache = RangeCache(self.state / "bounded", max_bytes=5)
        cache.get_or_fetch(NPIX7945.url, NPIX7945.expected_content_length, 0, 3, lambda: b"abcd")
        cache.get_or_fetch(NPIX7945.url, NPIX7945.expected_content_length, 4, 7, lambda: b"efgh")
        stats = cache.stats()
        self.assertLessEqual(stats["stored_bytes"], 5)
        self.assertEqual(stats["entries"], 1)
        self.assertEqual(stats["evictions"], 1)

    def test_verified_cache_survives_restart_without_refetch(self) -> None:
        if not (EVIDENCE / "multi_channel_result.json").is_file():
            self.skipTest("private raw-range evidence is not included in public checkouts")
        self.service = CubeSampleService(ServiceConfig(self.state, EVIDENCE))
        original = self.service.sample(self.payload())
        self.assertTrue(original["validation"]["genuine_evidence_match"])

        class NeverFetch:
            mode = "must-not-fetch"
            network_requests = 0
            network_bytes = 0
            identity = ProductIdentity(NPIX7945.url, NPIX7945.expected_content_length, None, None)

            def get(self, *_args):
                raise AssertionError("verified cache was not reused after restart")

        restarted = CubeSampleService(
            ServiceConfig(self.state, EVIDENCE), source_factory=lambda _product: NeverFetch()
        )
        result = restarted.sample(self.payload())
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreaterEqual(result["resources"]["cache_hits_this_call"], 15)
        self.assertEqual(result["resources"]["external_requests_this_call"], 0)

    def test_exact_range_cache_deduplicates_simultaneous_fetches(self) -> None:
        cache = RangeCache(self.state / "dedupe")
        calls = 0
        lock = threading.Lock()
        start = threading.Barrier(3)
        results: list[bytes] = []

        def fetch() -> bytes:
            nonlocal calls
            with lock:
                calls += 1
            time.sleep(0.05)
            return b"abcd"

        def worker() -> None:
            start.wait()
            results.append(cache.get_or_fetch(NPIX7945.url, NPIX7945.expected_content_length, 10, 13, fetch))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads: thread.start()
        start.wait()
        for thread in threads: thread.join()
        self.assertEqual(results, [b"abcd", b"abcd"])
        self.assertEqual(calls, 1)

    def test_service_allows_only_one_active_retrieval(self) -> None:
        if not (EVIDENCE / "multi_channel_result.json").is_file():
            self.skipTest("private raw-range evidence is not included in public checkouts")
        entered = threading.Event(); release = threading.Event()

        class BlockingSource(GenuineEvidenceSource):
            def get(inner_self, url, start, end):
                if not entered.is_set():
                    entered.set(); release.wait(timeout=5)
                return super().get(url, start, end)

        service = CubeSampleService(
            ServiceConfig(self.state / "concurrent", EVIDENCE),
            source_factory=lambda product: BlockingSource(EVIDENCE, product),
        )
        outcomes: list[object] = []

        def first() -> None:
            try: outcomes.append(service.sample(self.payload()))
            except Exception as exc: outcomes.append(exc)

        thread = threading.Thread(target=first); thread.start()
        self.assertTrue(entered.wait(timeout=5))
        with self.assertRaises(ServiceError) as caught:
            service.sample(self.payload(channel=0))
        self.assertEqual(caught.exception.code, "RETRIEVAL_BUSY")
        release.set(); thread.join(timeout=10)
        self.assertEqual(outcomes[0]["status"], "SUCCESS")

    def test_budget_accounting_survives_service_restart(self) -> None:
        reservation = self.service.budgets.ledger.reserve_request(
            method="HEAD", url=NPIX7945.url, planned_bytes=0
        )
        self.service.budgets.ledger.finish_request(reservation, state="completed", http_status=200)
        restarted = CubeSampleService(ServiceConfig(self.state))
        self.assertEqual(restarted.budgets.public_snapshot()["attempts"], 1)
        result = restarted.sample(self.payload())
        self.assertEqual(result["resources"]["budget"]["attempts"], 1)
        self.assertEqual(result["resources"]["external_requests_this_call"], 0)

    def test_exhausted_server_budget_fails_before_transport(self) -> None:
        for _ in range(40):
            reservation = self.service.budgets.ledger.reserve_request(
                method="HEAD", url=NPIX7945.url, planned_bytes=0
            )
            self.service.budgets.ledger.finish_request(reservation, state="completed", http_status=200)
        self.service._source_factory = lambda product: LiveAllowlistedSource(
            product, self.service.budgets, self.state / "artifacts",
            session=RedirectSession(),
        )
        with self.assertRaises(ServiceError) as caught:
            self.service.sample(self.payload())
        self.assertEqual(caught.exception.code, "ARCHIVE_BUDGET_EXHAUSTED")

    def test_redirects_and_non_allowlisted_urls_are_rejected(self) -> None:
        session = NoRedirectAllowlistedSession(NPIX7945.url, RedirectSession())
        with self.assertRaisesRegex(Exception, "redirects are forbidden"):
            session.head(NPIX7945.url)
        with self.assertRaisesRegex(Exception, "outside the fixed product allowlist"):
            session.get("https://example.test/cube.fits")
        with self.assertRaises(ServiceError):
            ProductResolver().resolve("https://irsa.ipac.caltech.edu/cube.fits")


if __name__ == "__main__":
    unittest.main()
