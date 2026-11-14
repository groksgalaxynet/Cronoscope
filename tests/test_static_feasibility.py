from __future__ import annotations

import functools
import threading
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


@contextmanager
def _static_server():
    root = Path(__file__).resolve().parents[1] / "static_feasibility"
    handler = functools.partial(_QuietStaticHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        worker.join(timeout=5)
        server.server_close()


@contextmanager
def _static_page(viewport: dict[str, int] | None = None):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            yield browser.new_page(viewport=viewport or {"width": 1280, "height": 900})
        finally:
            browser.close()


def _select_static_nasa_target(page, target_id: str) -> None:
    toggle = page.locator("#nasa-targets .panel-collapse-toggle")
    if toggle.get_attribute("aria-expanded") == "false":
        toggle.click()
    page.locator(f'#nasa-target-list [data-nasa-id="{target_id}"]').click()
    page.locator("#explore-observations").click()


def test_static_feasibility_page_is_a_self_contained_observation_explorer() -> None:
    root = Path(__file__).resolve().parents[1]
    page = (root / "static_feasibility" / "index.html").read_text()
    script = (root / "static_feasibility" / "app.js").read_text()
    combined = page + script

    assert "demo/catalog.json" in script
    assert "5122 Mucha (1989 AZ1)" in combined
    assert "Epoch A" in combined and "Epoch B" in combined
    assert "Blink A/B" in combined and "Sky / Track Explorer" in combined
    assert "Research evidence" in combined and "not a detection claim" in combined
    assert "$('observation-explorer').hidden=true" in script
    assert "if(hasTrajectory(t))views.push('trajectory')" in script
    assert "function renderTrajectory(t)" in script
    assert "not a measured continuous or orbital path" in script
    assert "/api/" not in combined
    assert "web_app.api" not in combined
    assert "irsa.ipac" not in combined.lower()
    assert "ssd.jpl" not in combined.lower()
    assert "horizons_file" not in combined.lower()
    assert 'fetch("http' not in combined and "fetch('http" not in combined


def test_static_demo_parity_assets_and_offline_controls_are_packaged() -> None:
    root = Path(__file__).resolve().parents[1]
    page = (root / "static_feasibility" / "index.html").read_text()
    panels = (root / "static_feasibility" / "static-panel-controls.js").read_text()
    gallery = (root / "static_feasibility" / "static-target-gallery.js").read_text()
    assets = root / "static_feasibility" / "assets"

    assert 'assets/cronologo.mp4' in page
    assert "static-panel-controls.js" in page and "static-target-gallery.js" in page
    assert "cronoscope.static-demo.panel-state.v1" in panels
    assert "prefers-reduced-motion" in panels
    assert all(name in gallery for name in ("M 31", "M 87", "M 42", "No substitute is shown"))
    assert (assets / "cronologo.mp4").is_file()
    assert all((assets / "target-gallery" / name).is_file() for name in ("m31-hubble.jpg", "m87-hubble.jpg", "m42-hubble.png"))


def test_static_demo_prioritizes_rw_aurigae_without_removing_mucha() -> None:
    root = Path(__file__).resolve().parents[1]
    page = (root / "static_feasibility" / "index.html").read_text()
    featured = (root / "static_feasibility" / "static-featured.js").read_text()

    assert "Start with featured example — RW Aurigae" in page
    assert "NASA Space Apps Challenge" in page
    assert "Open Mucha observation explorer" not in page
    assert 'data-nasa-id="rw-aur"' in featured
    assert 'data-id="5122"' not in featured


def test_rw_aurigae_guide_uses_existing_workspace_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    page = (root / "static_feasibility" / "index.html").read_text()
    guide = (root / "static_feasibility" / "static-guide.js").read_text()
    styles = (root / "static_feasibility" / "styles.css").read_text()

    assert all(f'data-guide="{step}"' in page for step in ("target", "time", "compare", "wavelength"))
    assert 'data-guide="motion"' not in page
    assert 'data-nasa-id="rw-aur"' in guide
    assert all(control in guide for control in ("observation-timeline", 'data-view="a"', 'data-view="spectrum"'))
    assert "font-size:clamp(2.25rem,3.3vw,2.75rem)" in styles


def test_static_target_switches_clear_stale_scientific_state() -> None:
    """No-imagery targets may not inherit image, wavelength, or spectrum data."""
    with _static_server() as base, _static_page() as page:
        page.goto(base)

        _select_static_nasa_target(page, "rw-aur")
        expect(page.locator("#observation-explorer")).to_contain_text("RW Aurigae")
        page.locator('#view-controls [data-view="spectrum"]').click()
        expect(page.locator("#spectral-explorer")).to_contain_text("RW Aurigae")

        _select_static_nasa_target(page, "epsilon-indi-b")
        expect(page.locator("#view-title")).to_have_text("NASA Challenge Target · Epsilon Indi B")
        expect(page.locator("#observation-explorer")).to_contain_text("NO VALIDATED CUTOUT")
        expect(page.locator("#science-frame")).to_be_hidden()
        expect(page.locator("#science-image")).not_to_have_attribute("src", ".+")
        expect(page.locator("#wavelength-detail")).to_be_hidden()
        expect(page.locator("#wavelength-detail")).to_be_empty()
        expect(page.locator("#spectral-explorer")).to_be_hidden()
        expect(page.locator("#spectral-explorer")).to_be_empty()
        assert "RW Aurigae" not in page.locator("#observation-explorer").inner_text()

        _select_static_nasa_target(page, "barnards-star")
        expect(page.locator("#observation-explorer")).to_contain_text("Barnard's Star")
        expect(page.locator("#science-image")).to_have_attribute("src", "demo/nasa-barnard-a.png")
        assert "RW Aurigae" not in page.locator("#observation-explorer").inner_text()

        # Rapid changes invalidate pending spectrum work before the final target renders.
        for target_id in ("rw-aur", "epsilon-indi-b", "barnards-star", "rw-aur"):
            page.locator(f'#nasa-target-list [data-nasa-id="{target_id}"]').click()
        page.locator("#explore-observations").click()
        expect(page.locator("#observation-explorer")).to_contain_text("RW Aurigae")
        expect(page.locator("#science-image")).to_have_attribute("src", "demo/nasa-rw-aur-a.png")
        assert "Barnard's Star" not in page.locator("#observation-explorer").inner_text()


def test_static_coordinate_matching_provenance_and_display_zoom() -> None:
    with _static_server() as base, _static_page() as page:
        page.goto(base)

        page.locator("#coordinate-ra").fill("29.20697")
        page.locator("#coordinate-dec").fill("-2.32737")
        page.locator("#coordinate-form button").click()
        expect(page.locator("#coordinate-status")).to_contain_text("5122 Mucha")
        expect(page.locator("#selected-name")).to_have_text("5122 Mucha (1989 AZ1)")
        expect(page.locator("#science-image")).to_have_attribute("src", "demo/5122-target-a.png")
        page.locator("#science-image-zoom-in").click()
        expect(page.locator("#science-image-scale")).to_have_text("125%")

        page.locator("#coordinate-ra").fill("360")
        page.locator("#coordinate-dec").fill("0")
        page.locator("#coordinate-form button").click()
        expect(page.locator("#coordinate-status")).to_contain_text("less than 360°")

        _select_static_nasa_target(page, "rw-aur")
        expect(page.locator("#static-provenance-detail")).to_contain_text("SPHEREx Quick Release 2")
        expect(page.locator("#static-provenance-detail")).to_contain_text("Difference status")
        expect(page.locator("#static-provenance-detail")).to_contain_text("No validated registered difference product")


def test_static_page_has_no_external_requests_and_mobile_controls_fit() -> None:
    with _static_server() as base, _static_page({"width": 390, "height": 844}) as page:
        requests: list[str] = []
        page.on("request", lambda request: requests.append(request.url))
        page.goto(base)
        page.wait_for_selector("#coordinate-form")
        assert all(url.startswith(base) for url in requests)
        form = page.locator("#coordinate-form").bounding_box()
        button = page.locator("#coordinate-form button").bounding_box()
        assert form is not None and button is not None
        assert button["x"] >= form["x"] and button["x"] + button["width"] <= form["x"] + form["width"] + 1
