"""Server-owned allowlist for verified SPHEREx DR1 cube products."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .errors import ServiceError


OFFICIAL_HOST = "irsa.ipac.caltech.edu"


@dataclass(frozen=True)
class AllowedProduct:
    product_id: str
    filename: str
    release: str
    collection: str
    url: str
    expected_content_length: int
    expected_hdu_sequence: tuple[str, ...]

    def validate_static_identity(self) -> None:
        parsed = urlparse(self.url)
        if parsed.scheme != "https" or parsed.hostname != OFFICIAL_HOST:
            raise RuntimeError("allowlisted product does not use the approved HTTPS archive host")
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            raise RuntimeError("allowlisted product contains an unsupported authority")
        if not parsed.path.endswith("/Npix7945_cube.fits") or parsed.query or parsed.fragment:
            raise RuntimeError("allowlisted product path is not the verified FITS identity")
        if self.expected_content_length != 320_909_760:
            raise RuntimeError("allowlisted product length is not the verified identity")


NPIX7945 = AllowedProduct(
    product_id="Npix7945_cube",
    filename="Npix7945_cube.fits",
    release="SPHEREx DR1",
    collection="spherex_dr1_cube",
    url=(
        "https://irsa.ipac.caltech.edu/ibe/data/spherex/dr1/hips5_cube/"
        "hips_20261026/Norder5/Dir0/Npix7945_cube.fits"
    ),
    expected_content_length=320_909_760,
    expected_hdu_sequence=(
        "PRIMARY", "IMAGE", "NHITS", "FLAGS", "SPECTRAL_CHANNELS", "WCS-WAVE"
    ),
)

PRODUCTS = {NPIX7945.product_id: NPIX7945}


class ProductResolver:
    """Resolve opaque client IDs; URLs and paths are never client inputs."""

    def __init__(self) -> None:
        for product in PRODUCTS.values():
            product.validate_static_identity()

    def resolve(self, product_id: object) -> AllowedProduct:
        if not isinstance(product_id, str):
            raise ServiceError("INVALID_PRODUCT_ID", "product_id must be a string")
        product = PRODUCTS.get(product_id)
        if product is None:
            raise ServiceError(
                "UNKNOWN_PRODUCT",
                "The requested product is not in the experimental service allowlist.",
                404,
            )
        return product
