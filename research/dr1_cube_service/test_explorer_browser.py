from __future__ import annotations

import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from wsgiref.simple_server import make_server

from playwright.sync_api import expect, sync_playwright

from research.dr1_cube_service.api import create_app
from research.dr1_cube_service.service import CubeSampleService, ServiceConfig

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (
    ROOT / "research" / "dr1_cube_reader" / "evidence" /
    "CRONOSCOPE_DR1_5_NPIX7945_MULTI_2026_11_15"
)
EXPECTED_WAVELENGTHS = {
    "0": "0.753000021 µm",
    "20": "1.195000052 µm",
    "100": "4.951000214 µm",
}


@contextmanager
def running_explorer():
    with tempfile.TemporaryDirectory() as temporary:
        service = CubeSampleService(ServiceConfig(Path(temporary), EVIDENCE))
        server = make_server("127.0.0.1", 0, create_app(service))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}", service
        finally:
            server.shutdown(); thread.join(timeout=5); server.server_close()


def test_explorer_loads_all_verified_samples_and_switches_science_arrays() -> None:
    errors: list[str] = []
    with running_explorer() as (base, service), sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.goto(base + "/experimental/dr1-cube")
        expect(page.locator("h1")).to_have_text("Experimental Wavelength Explorer")
        expect(page.locator("#channel option")).to_have_count(3)
        expect(page.locator("#region option")).to_have_count(2)

        for channel, wavelength in EXPECTED_WAVELENGTHS.items():
            page.locator("#channel").select_option(channel)
            for region in ("90,107", "94,107"):
                page.locator("#region").select_option(region)
                page.locator("#load-sample").click()
                expect(page.locator("#status")).to_have_attribute("data-state", "success", timeout=15000)
                expect(page.locator("#grid .pixel")).to_have_count(16)
                expect(page.locator("#wavelength")).to_contain_text(wavelength)
                expect(page.locator("#provenance")).to_contain_text("Npix7945_cube.fits")
                expect(page.locator("#provenance")).to_contain_text("SPHEREx DR1")
                expect(page.locator("#validation")).to_contain_text("Genuine saved evidence matched exactly")
                expect(page.locator("#array-note")).to_contain_text("missing values: 0")

        reference = next(
            sample for sample in service._source(service.resolver.resolve("Npix7945_cube")).reference["samples"]
            if sample["request"]["channel_zero_based"] == 100 and sample["request"]["x"] == 94
        )
        expect(page.locator("#unit")).to_have_text("MJy/sr")
        expect(page.locator("#grid .pixel").first).to_have_attribute("data-value", str(reference["arrays"]["IMAGE"]["values"][0][0]))
        page.get_by_role("button", name="NHITS").click()
        expect(page.locator("#unit")).to_have_text("contribution count")
        expect(page.locator("#grid .pixel").first).to_have_attribute("data-value", str(reference["arrays"]["NHITS"]["values"][0][0]))
        page.get_by_role("button", name="RAW FLAGS").click()
        expect(page.locator("#unit")).to_have_text("raw integer bitmap · uninterpreted")
        expect(page.locator("#grid .pixel").first).to_have_attribute("data-value", str(reference["arrays"]["FLAGS"]["values"][0][0]))

        page.route("**/api/experimental/dr1/cube/sample", lambda route: route.fulfill(
            status=200, content_type="application/json",
            body='{"status":"ERROR","error":{"message":"Controlled service unavailable"}}',
        ))
        page.locator("#load-sample").click()
        expect(page.locator("#status")).to_have_attribute("data-state", "error")
        expect(page.locator("#status")).to_contain_text("Unable to load sample")
        browser.close()
        assert service.budgets.public_snapshot()["attempts"] == 0
    assert errors == []
