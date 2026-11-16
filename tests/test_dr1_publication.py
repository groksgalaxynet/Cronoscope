"""Self-contained public acceptance tests for the DR1 image integration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from astropy.io import fits

from cronoscope_pipeline.discovery import DEFAULT_COLLECTION, SUPPORTED_COLLECTIONS
from cronoscope_pipeline.fits_normalization import normalize_fits_product
from cronoscope_pipeline.models import (
    FitsValidation,
    ObservationRecord,
    RetrievalResult,
    RetrievalStatus,
)
from cronoscope_pipeline.orchestrator import release_compatibility
from cronoscope_pipeline.retrieval import bounded_access_url, validate_dr1_image_file


def observation(collection: str, detector: str = "SPHEREx-D3") -> ObservationRecord:
    return ObservationRecord(
        "public-fixture", 11.888, -25.2882, 61000.0, 61000.01,
        1.1e-6, 1.2e-6, detector, 2, "image",
        "https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/level2/example.fits",
        "image/fits", 1024, collection, "SPHEREx", None, None,
        raw_identifiers={"obs_publisher_did": f"ivo://irsa/{collection}/public-fixture"},
        query_ra_deg=11.888, query_dec_deg=-25.2882, query_radius_deg=0.03,
    )


def write_synthetic_dr1(path: Path) -> None:
    image = fits.ImageHDU(np.arange(16, dtype=np.float32).reshape(4, 4), name="IMAGE")
    image.header["BUNIT"] = "MJy / sr"
    image.header["DETECTOR"] = "3"
    flags = fits.ImageHDU(np.zeros((4, 4), dtype=np.int32), name="FLAGS")
    variance = fits.ImageHDU(np.ones((4, 4), dtype=np.float32), name="VARIANCE")
    variance.header["BUNIT"] = "MJy2 / sr2"
    zodi = fits.ImageHDU(np.zeros((4, 4), dtype=np.float32), name="ZODI")
    epsf = fits.BinTableHDU.from_columns(
        [fits.Column(name="VALUE", format="E", array=np.asarray([1.0], dtype=np.float32))],
        name="EPSF",
    )
    wave = fits.BinTableHDU.from_columns(
        [
            fits.Column(name="X", format="E", array=np.asarray([0.0], dtype=np.float32)),
            fits.Column(name="Y", format="E", array=np.asarray([0.0], dtype=np.float32)),
            fits.Column(name="VALUES", format="E", array=np.asarray([1.15], dtype=np.float32)),
        ],
        name="WCS-WAVE",
    )
    fits.HDUList([fits.PrimaryHDU(), image, flags, variance, zodi, epsf, wave]).writeto(path)


class Dr1PublicationTests(unittest.TestCase):
    def test_supported_release_boundary_is_explicit_and_cross_release_is_blocked(self) -> None:
        self.assertEqual(DEFAULT_COLLECTION, "spherex_dr1")
        self.assertEqual(
            SUPPORTED_COLLECTIONS,
            {"spherex_dr1", "spherex_dr1_deep", "spherex_qr2", "spherex_qr3"},
        )
        for collection in SUPPORTED_COLLECTIONS:
            self.assertIsNone(release_compatibility(observation(collection), observation(collection)))
        self.assertIn(
            "Cross-collection comparison is blocked",
            release_compatibility(observation("spherex_dr1"), observation("spherex_qr3")),
        )

    def test_six_wide_detectors_and_deep_d1_remain_selectable(self) -> None:
        app_source = (Path(__file__).parents[1] / "web_app" / "static" / "app.js").read_text()
        for detector in range(1, 7):
            self.assertIn(f'"SPHEREx-D{detector}"', app_source)
        self.assertIn('value="spherex_dr1_deep"', app_source)

    def test_dr1_cutout_is_bounded_and_query_scoped(self) -> None:
        url = bounded_access_url(observation("spherex_dr1"))
        self.assertIn("center=11.888%2C-25.2882", url)
        self.assertIn("size=0.06", url)

    def test_dr1_arrays_units_and_provenance_stay_aligned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "synthetic-dr1.fits"
            write_synthetic_dr1(path)
            validation = validate_dr1_image_file(path)
            self.assertTrue(validation.valid, validation.message)
            record = observation("spherex_dr1")
            retrieval = RetrievalResult(
                RetrievalStatus.CACHE_HIT, "public-fixture", str(path), record.access_url,
                path.stat().st_size, record.observation_id, FitsValidation(True, 7),
            )
            product = normalize_fits_product(retrieval, record)
            self.assertEqual(product.image.shape, product.quality_flags.shape)
            self.assertEqual(product.image.shape, product.variance.shape)
            self.assertEqual(product.image_unit, "MJy / sr")
            self.assertEqual(product.variance_unit, "MJy2 / sr2")
            self.assertEqual(product.collection, "spherex_dr1")
            self.assertEqual(product.source_url, record.access_url)


if __name__ == "__main__":
    unittest.main()
