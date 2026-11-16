"""Localhost-only WSGI API for the experimental DR1 cube service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Iterable
from wsgiref.simple_server import make_server

from .errors import ServiceError
from .service import CubeSampleService, ServiceConfig

SAMPLE_PATH = "/api/experimental/dr1/cube/sample"
HEALTH_PATH = "/api/experimental/dr1/cube/health"
EXPLORER_PATH = "/experimental/dr1-cube"
ASSET_PATHS = {
    "/experimental/dr1-cube/explorer.css": ("explorer.css", "text/css; charset=utf-8"),
    "/experimental/dr1-cube/explorer.js": ("explorer.js", "text/javascript; charset=utf-8"),
}
MAX_REQUEST_BODY_BYTES = 4096

STATUS_TEXT = {
    200: "200 OK",
    400: "400 Bad Request",
    404: "404 Not Found",
    405: "405 Method Not Allowed",
    413: "413 Payload Too Large",
    415: "415 Unsupported Media Type",
    422: "422 Unprocessable Entity",
    429: "429 Too Many Requests",
    500: "500 Internal Server Error",
    502: "502 Bad Gateway",
    503: "503 Service Unavailable",
}


def _encoded(value: dict[str, Any]) -> bytes:
    return json.dumps(value, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _response(
    start_response: Callable[..., Any], status: int, value: dict[str, Any],
) -> Iterable[bytes]:
    body = _encoded(value)
    start_response(
        STATUS_TEXT[status],
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )
    return [body]


def _asset_response(
    start_response: Callable[..., Any], path: Path, content_type: str,
) -> Iterable[bytes]:
    body = path.read_bytes()
    start_response("200 OK", [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
    ])
    return [body]


class CubeServiceApplication:
    def __init__(self, service: CubeSampleService) -> None:
        self.service = service

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "GET").upper()
        asset_root = Path(__file__).with_name("explorer")
        if path == EXPLORER_PATH:
            if method != "GET":
                return _response(start_response, 405, ServiceError("METHOD_NOT_ALLOWED", "Use GET for the explorer.", 405).envelope())
            return _asset_response(start_response, asset_root / "index.html", "text/html; charset=utf-8")
        if path in ASSET_PATHS:
            if method != "GET":
                return _response(start_response, 405, ServiceError("METHOD_NOT_ALLOWED", "Use GET for explorer assets.", 405).envelope())
            filename, content_type = ASSET_PATHS[path]
            return _asset_response(start_response, asset_root / filename, content_type)
        if path == HEALTH_PATH:
            if method != "GET":
                return _response(start_response, 405, ServiceError("METHOD_NOT_ALLOWED", "Use GET for health.", 405).envelope())
            return _response(start_response, 200, {
                "classification": "EXPERIMENTAL_DR1_CUBE_SERVICE_HEALTH",
                "status": "READY",
                "live_archive_enabled": self.service.config.enable_live,
                "allowlisted_products": ["Npix7945_cube"],
                "max_concurrent_archive_retrievals": 1,
            })
        if path != SAMPLE_PATH:
            return _response(start_response, 404, ServiceError("NOT_FOUND", "Route not found.", 404).envelope())
        if method != "POST":
            return _response(start_response, 405, ServiceError("METHOD_NOT_ALLOWED", "Use POST for cube sampling.", 405).envelope())
        content_type = environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return _response(start_response, 415, ServiceError("UNSUPPORTED_MEDIA_TYPE", "Content-Type must be application/json.", 415).envelope())
        try:
            length = int(environ.get("CONTENT_LENGTH", ""))
        except (TypeError, ValueError):
            length = -1
        if length <= 0:
            return _response(start_response, 400, ServiceError("INVALID_CONTENT_LENGTH", "A positive Content-Length is required.").envelope())
        if length > MAX_REQUEST_BODY_BYTES:
            return _response(start_response, 413, ServiceError("REQUEST_BODY_TOO_LARGE", "Request body exceeds 4096 bytes.", 413).envelope())
        try:
            body = environ["wsgi.input"].read(length)
            if len(body) != length:
                raise ServiceError("TRUNCATED_REQUEST", "Request body was truncated.")
            payload = json.loads(body.decode("utf-8"))
            result = self.service.sample(payload)
            return _response(start_response, 200, result)
        except UnicodeDecodeError:
            error = ServiceError("INVALID_JSON", "Request body must be UTF-8 JSON.")
        except json.JSONDecodeError:
            error = ServiceError("INVALID_JSON", "Request body is not valid JSON.")
        except ServiceError as exc:
            error = exc
        except Exception:
            error = ServiceError(
                "INTERNAL_ERROR", "The experimental service failed safely without exposing a traceback.", 500
            )
        return _response(start_response, error.http_status, error.envelope())


def create_app(service: CubeSampleService) -> CubeServiceApplication:
    return CubeServiceApplication(service)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local experimental SPHEREx DR1 cube service")
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be in 1..65535")
    evidence_root = None if args.enable_live else args.evidence_root
    service = CubeSampleService(ServiceConfig(
        state_dir=args.state_dir,
        evidence_root=evidence_root,
        enable_live=args.enable_live,
    ))
    with make_server("127.0.0.1", args.port, create_app(service)) as server:
        print(f"Experimental DR1 cube service listening on http://127.0.0.1:{args.port}", flush=True)
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
