from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from research.dr1_cube_service.api import EXPLORER_PATH, SAMPLE_PATH, create_app
from research.dr1_cube_service.service import CubeSampleService, ServiceConfig

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    ROOT / "research" / "dr1_cube_reader" / "evidence" /
    "CRONOSCOPE_DR1_5_NPIX7945_MULTI_2026_11_15"
)


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        service = CubeSampleService(ServiceConfig(Path(self.temporary.name)))
        self.app = create_app(service)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def call(self, path=SAMPLE_PATH, method="POST", payload=None, content_type="application/json", raw=None):
        environ: dict[str, object] = {}
        setup_testing_defaults(environ)
        environ["PATH_INFO"] = path; environ["REQUEST_METHOD"] = method
        body = raw if raw is not None else json.dumps(payload if payload is not None else {}).encode()
        environ["CONTENT_TYPE"] = content_type
        environ["CONTENT_LENGTH"] = str(len(body))
        environ["wsgi.input"] = io.BytesIO(body)
        captured = {}

        def start_response(status, headers):
            captured["status"] = status; captured["headers"] = dict(headers)

        response = json.loads(b"".join(self.app(environ, start_response)))
        return captured, response

    @staticmethod
    def payload():
        return {"product_id": "Npix7945_cube", "channel": 20, "x": 90, "y": 107, "width": 4, "height": 4}

    def test_valid_http_envelope_has_science_provenance_and_no_cors(self) -> None:
        captured, response = self.call(payload=self.payload())
        self.assertEqual(captured["status"], "200 OK")
        self.assertEqual(response["classification"], "EXPERIMENTAL_DR1_CUBE_SAMPLE")
        self.assertTrue(response["validation"]["genuine_evidence_match"])
        self.assertTrue(response["validation"]["public_result_replay"])
        self.assertFalse(response["validation"]["current_raw_range_decode_performed"])
        self.assertEqual(response["resources"]["external_requests_this_call"], 0)
        self.assertNotIn("Access-Control-Allow-Origin", captured["headers"])
        self.assertEqual(captured["headers"]["Cache-Control"], "no-store")

    def test_unknown_route_method_and_content_type_fail_closed(self) -> None:
        self.assertEqual(self.call(path="/api/other", payload=self.payload())[0]["status"], "404 Not Found")
        self.assertEqual(self.call(method="GET", payload=self.payload())[0]["status"], "405 Method Not Allowed")
        self.assertEqual(self.call(payload=self.payload(), content_type="text/plain")[0]["status"], "415 Unsupported Media Type")

    def test_explorer_and_fixed_assets_are_served_with_strict_security_headers(self) -> None:
        for path, expected_type in (
            (EXPLORER_PATH, "text/html"),
            (EXPLORER_PATH + "/explorer.css", "text/css"),
            (EXPLORER_PATH + "/explorer.js", "text/javascript"),
        ):
            environ: dict[str, object] = {}
            setup_testing_defaults(environ)
            environ["PATH_INFO"] = path; environ["REQUEST_METHOD"] = "GET"
            captured = {}
            body = b"".join(self.app(environ, lambda status, headers: captured.update(status=status, headers=dict(headers))))
            self.assertEqual(captured["status"], "200 OK")
            self.assertTrue(captured["headers"]["Content-Type"].startswith(expected_type))
            self.assertIn("default-src 'self'", captured["headers"]["Content-Security-Policy"])
            self.assertNotIn(b"http://", body)
        self.assertIn(b"Experimental Wavelength Explorer", self._asset(EXPLORER_PATH))

    def _asset(self, path: str) -> bytes:
        environ: dict[str, object] = {}
        setup_testing_defaults(environ)
        environ["PATH_INFO"] = path; environ["REQUEST_METHOD"] = "GET"
        return b"".join(self.app(environ, lambda *_args: None))

    def test_invalid_json_and_unknown_parameters_do_not_expose_tracebacks(self) -> None:
        captured, response = self.call(raw=b"{broken")
        self.assertEqual(captured["status"], "400 Bad Request")
        self.assertEqual(response["error"]["code"], "INVALID_JSON")
        self.assertNotIn("traceback", json.dumps(response).lower())
        captured, response = self.call(payload={**self.payload(), "url": "http://localhost/private"})
        self.assertEqual(captured["status"], "400 Bad Request")
        self.assertEqual(response["error"]["code"], "UNKNOWN_PARAMETERS")

    def test_oversized_body_is_rejected_without_reading_or_processing(self) -> None:
        environ: dict[str, object] = {}
        setup_testing_defaults(environ)
        environ.update({
            "PATH_INFO": SAMPLE_PATH, "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": "4097",
            "wsgi.input": io.BytesIO(b""),
        })
        captured = {}
        response = json.loads(b"".join(self.app(environ, lambda status, _headers: captured.update(status=status))))
        self.assertEqual(captured["status"], "413 Payload Too Large")
        self.assertEqual(response["error"]["code"], "REQUEST_BODY_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
