from __future__ import annotations

import io
import unittest
from pathlib import Path

import numpy as np
from astropy.io import fits

from research.dr1_cube_reader.reader import (
    BlankChannelError,
    CubeReader,
    EvidenceUnavailableError,
    InMemoryFitsSource,
    RegionRequest,
    SavedEvidenceSource,
    UnsupportedCubeError,
)


LIVE_ROOT = Path(__file__).parents[1] / "dr1_cube_range" / "evidence" / "CRONOSCOPE_DR1_3L_NPIX7945_2026_11_15"


def synthetic_cube(*, missing=None, nhits_float=False, compressed=False):
    shape=(102,4,4)
    image=np.arange(np.prod(shape),dtype=np.float32).reshape(shape)/10
    image[10,1,1]=np.nan
    nhits=np.full(shape,7,dtype=np.float32 if nhits_float else np.int32)
    flags=np.zeros(shape,dtype=np.int32); flags[:,2:,2:]=8
    primary=fits.PrimaryHDU(); primary.header["BLANKCH"]="D3:17,D4:01"
    image_hdu=fits.ImageHDU(image,name="IMAGE"); image_hdu.header["BUNIT"]="MJy/sr"
    if compressed: image_hdu.header["ZIMAGE"]=True
    hdus=[primary]
    for name,hdu in (("IMAGE",image_hdu),("NHITS",fits.ImageHDU(nhits,name="NHITS")),("FLAGS",fits.ImageHDU(flags,name="FLAGS"))):
        if name!=missing: hdus.append(hdu)
    channels=np.arange(102,dtype=np.int16)
    spectral=fits.BinTableHDU.from_columns([
        fits.Column(name="DETECTOR",format="I",array=channels//17+1),
        fits.Column(name="SUBCHAN",format="I",array=channels%17+1),
        fits.Column(name="WAVELENGTH",format="E",array=0.75+channels*0.01),
        fits.Column(name="WL_MIN",format="E",array=0.745+channels*0.01),
        fits.Column(name="WL_MAX",format="E",array=0.755+channels*0.01),
        fits.Column(name="R",format="E",array=np.full(102,40,dtype=np.float32)),
        fits.Column(name="R_STD",format="E",array=np.full(102,0.5,dtype=np.float32)),
        fits.Column(name="BANDWIDTH",format="E",array=np.full(102,0.01,dtype=np.float32)),
    ],name="SPECTRAL_CHANNELS")
    wave=fits.BinTableHDU.from_columns([
        fits.Column(name="PLANE",format="102J",array=[np.arange(102,dtype=np.int32)]),
        fits.Column(name="WAVELENGTHS",format="102E",array=[0.75+np.arange(102,dtype=np.float32)*0.01]),
        fits.Column(name="BANDWIDTHS",format="102E",array=[np.full(102,0.01,dtype=np.float32)]),
    ],name="WCS-WAVE")
    if missing!="SPECTRAL_CHANNELS": hdus.append(spectral)
    if missing!="WCS-WAVE": hdus.append(wave)
    stream=io.BytesIO(); fits.HDUList(hdus).writeto(stream)
    return stream.getvalue(),image,nhits,flags


class ReaderTests(unittest.TestCase):
    def reader(self, **kwargs):
        raw,*arrays=synthetic_cube(**kwargs)
        return CubeReader(InMemoryFitsSource(raw),strict_spherex_shape=False).open(),arrays

    @unittest.skipUnless(
        LIVE_ROOT.is_dir(),
        "private genuine-response evidence is intentionally not distributed",
    )
    def test_genuine_dr13l_replay_exactly_matches(self):
        result=CubeReader(SavedEvidenceSource(LIVE_ROOT)).open().read_region(RegionRequest(20,90,107,4,4))
        self.assertEqual(result["validation"]["classification"],"GENUINE_DR1_3L_REPLAY_MATCH")
        self.assertTrue(result["validation"]["reference_match"])
        self.assertEqual(result["resources"]["network_requests"],0)
        self.assertEqual(result["resources"]["network_bytes"],0)
        self.assertEqual(result["science"]["image_unit"],"MJy/sr")
        self.assertEqual(result["science"]["channel"]["DETECTOR"],2)
        self.assertEqual(result["science"]["channel"]["SUBCHAN"],4)
        self.assertEqual(result["ranges"]["IMAGE"]["sha256"],"914336796bdaf8e8da794f9e1f8dfd69f04989f09ad9b4805d2fad1211d48ee7")

    def test_other_valid_channel_and_different_region(self):
        reader,(image,nhits,flags)=self.reader()
        result=reader.read_region(RegionRequest(100,1,0,3,2))
        np.testing.assert_array_equal(result["arrays"]["IMAGE"]["values"],image[100,0:2,1:4])
        np.testing.assert_array_equal(result["arrays"]["NHITS"]["values"],nhits[100,0:2,1:4])
        np.testing.assert_array_equal(result["arrays"]["FLAGS"]["values"],flags[100,0:2,1:4])

    def test_boundary_pixel(self):
        reader,_=self.reader(); result=reader.read_region(RegionRequest(0,3,3,1,1))
        self.assertEqual(result["coordinates"]["pixel_extent_zero_based_inclusive"],[3,3,3,3])

    def test_invalid_channels(self):
        reader,_=self.reader()
        for channel in (-1,102):
            with self.subTest(channel=channel),self.assertRaises(ValueError):
                reader.read_region(RegionRequest(channel,0,0,1,1))

    def test_blank_channels_require_explicit_acknowledgement(self):
        reader,_=self.reader()
        for channel in (51,52):
            with self.subTest(channel=channel),self.assertRaises(BlankChannelError):
                reader.read_region(RegionRequest(channel,0,0,1,1))
        result=reader.read_region(RegionRequest(51,0,0,1,1,allow_blank_channel=True))
        self.assertTrue(result["request"]["blank_channel"])

    def test_spatial_bounds_and_maximum(self):
        reader,_=self.reader()
        RegionRequest(0,480,480,32,32).validate(512,512,102)
        for request in (RegionRequest(0,-1,0,1,1),RegionRequest(0,0,0,5,1),RegionRequest(0,0,0,33,1)):
            with self.subTest(request=request),self.assertRaises(ValueError): reader.read_region(request)

    def test_nan_is_preserved(self):
        reader,_=self.reader(); result=reader.read_region(RegionRequest(10,1,1,1,1))
        self.assertEqual(result["arrays"]["IMAGE"]["values"],[[None]])
        self.assertEqual(result["arrays"]["IMAGE"]["finite_count"],0)

    def test_missing_extension_is_rejected(self):
        raw,*_=synthetic_cube(missing="FLAGS")
        with self.assertRaises(UnsupportedCubeError):
            CubeReader(InMemoryFitsSource(raw),strict_spherex_shape=False).open()

    def test_wrong_data_type_is_rejected(self):
        raw,*_=synthetic_cube(nhits_float=True)
        with self.assertRaisesRegex(UnsupportedCubeError,"data types"):
            CubeReader(InMemoryFitsSource(raw),strict_spherex_shape=False).open()

    def test_compressed_image_marker_is_rejected(self):
        raw,*_=synthetic_cube(compressed=True)
        with self.assertRaisesRegex(UnsupportedCubeError,"compressed"):
            CubeReader(InMemoryFitsSource(raw),strict_spherex_shape=False).open()

    def test_corrupted_header_is_rejected(self):
        raw,*_=synthetic_cube(); corrupted=b"X"+raw[1:]
        with self.assertRaises(UnsupportedCubeError):
            CubeReader(InMemoryFitsSource(corrupted),strict_spherex_shape=False).open()

    def test_truncated_fixture_is_rejected(self):
        raw,*_=synthetic_cube(); truncated=raw[:-100]
        with self.assertRaises(UnsupportedCubeError):
            CubeReader(InMemoryFitsSource(truncated),strict_spherex_shape=False).open()

    @unittest.skipUnless(
        LIVE_ROOT.is_dir(),
        "private genuine-response evidence is intentionally not distributed",
    )
    def test_saved_evidence_rejects_unavailable_region_without_network(self):
        source=SavedEvidenceSource(LIVE_ROOT); reader=CubeReader(source).open()
        with self.assertRaises(EvidenceUnavailableError):
            reader.read_region(RegionRequest(20,0,0,1,1))
        self.assertEqual(source.network_requests,0)


if __name__ == "__main__": unittest.main()
