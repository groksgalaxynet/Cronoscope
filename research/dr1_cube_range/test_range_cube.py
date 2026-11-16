from __future__ import annotations

import unittest
import io
from types import SimpleNamespace

import numpy as np
from astropy.io import fits

from research.dr1_cube_range.range_cube import (
    FITS_BLOCK, BoundedRangeClient, FitsLayoutError, HduLayout, ProductIdentity,
    RangeResponseError, TransferBudgetExceeded, TransferLedger, data_size,
    decode_sample, inspect_layout, padded, parse_header, sample_span,
)


def header_bytes(**values):
    header = fits.Header()
    for key, value in values.items(): header[key] = value
    return header.tostring(endcard=True, padding=True).encode("ascii")


def layout(bitpix=-32, axes=(4, 3, 2), **kwargs):
    return HduLayout(1, "IMAGE", 0, FITS_BLOCK, FITS_BLOCK, 0, 0, 0, bitpix, len(axes), axes,
                     0, 1, kwargs.get("bscale", 1.0), kwargs.get("bzero", 0.0), kwargs.get("blank"), b"", fits.Header())


class FakeResponse:
    def __init__(self, status, body=b"", headers=None, url="https://x/cube.fits"):
        self.status_code=status; self.body=body; self.headers=headers or {}; self.url=url; self.history=[]; self.closed=False
    def close(self): self.closed=True
    def iter_content(self, chunk_size):
        if self.body: yield self.body
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, response): self.response=response
    def get(self, *_a, **_k): return self.response


class ByteClient:
    def __init__(self, raw):
        self.raw=raw
        self.identity=ProductIdentity("https://x/cube.fits",len(raw),None,None)
    def get(self, _url, start, end): return self.raw[start:end+1]


class RangeCubeTests(unittest.TestCase):
    def test_padding(self):
        self.assertEqual(padded(0),0); self.assertEqual(padded(1),2880); self.assertEqual(padded(2880),2880)

    def test_header_parsing_and_alignment(self):
        raw=header_bytes(SIMPLE=True,BITPIX=8,NAXIS=0)
        header,length,_=parse_header(raw)
        self.assertTrue(header["SIMPLE"]); self.assertEqual(length,FITS_BLOCK)

    def test_header_rejects_missing_end(self):
        with self.assertRaises(FitsLayoutError): parse_header(b" "*FITS_BLOCK)

    def test_data_size_image_and_table(self):
        image=fits.Header({"BITPIX":-32,"NAXIS":3,"NAXIS1":512,"NAXIS2":512,"NAXIS3":102})
        table=fits.Header({"BITPIX":8,"NAXIS":2,"NAXIS1":32,"NAXIS2":102,"PCOUNT":0,"GCOUNT":1})
        self.assertEqual(data_size(image),512*512*102*4); self.assertEqual(data_size(table),32*102)

    def test_data_size_empty_primary(self):
        primary=fits.Header({"BITPIX":8,"NAXIS":0})
        self.assertEqual(data_size(primary),0)

    def test_hdu_offsets_follow_real_fits_padding(self):
        hdus=[fits.PrimaryHDU()]
        for name in ("IMAGE","NHITS","FLAGS"):
            hdus.append(fits.ImageHDU(np.zeros((2,3,4),dtype=np.float32 if name=="IMAGE" else np.int32),name=name))
        hdus.append(fits.BinTableHDU.from_columns([fits.Column(name="W",format="E",array=[1.0,2.0])],name="SPECTRAL_CHANNELS"))
        hdus.append(fits.BinTableHDU.from_columns([fits.Column(name="W",format="E",array=[1.0])],name="WCS-WAVE"))
        stream=io.BytesIO(); fits.HDUList(hdus).writeto(stream)
        layouts=inspect_layout(ByteClient(stream.getvalue()),"https://x/cube.fits")
        self.assertEqual(tuple(item.name for item in layouts),("PRIMARY","IMAGE","NHITS","FLAGS","SPECTRAL_CHANNELS","WCS-WAVE"))
        for current,next_item in zip(layouts,layouts[1:]): self.assertEqual(current.next_header_start,next_item.header_start)
        self.assertEqual(layouts[-1].next_header_start,len(stream.getvalue()))

    def test_offline_aligned_three_array_extraction_matches_astropy(self):
        image=np.arange(2*3*4,dtype=np.float32).reshape(2,3,4)
        image[1,1,1]=np.nan
        nhits=np.arange(2*3*4,dtype=np.int32).reshape(2,3,4)+10
        flags=(np.arange(2*3*4,dtype=np.int32).reshape(2,3,4)%4)
        hdus=[fits.PrimaryHDU(),fits.ImageHDU(image,name="IMAGE"),fits.ImageHDU(nhits,name="NHITS"),fits.ImageHDU(flags,name="FLAGS")]
        hdus.append(fits.BinTableHDU.from_columns([fits.Column(name="W",format="E",array=[1.0,2.0])],name="SPECTRAL_CHANNELS"))
        hdus.append(fits.BinTableHDU.from_columns([fits.Column(name="W",format="E",array=[1.0])],name="WCS-WAVE"))
        stream=io.BytesIO(); fits.HDUList(hdus).writeto(stream); raw_file=stream.getvalue()
        layouts=inspect_layout(ByteClient(raw_file),"https://x/cube.fits")
        by_name={item.name:item for item in layouts}
        expected={"IMAGE":image[1,1:3,1:3],"NHITS":nhits[1,1:3,1:3],"FLAGS":flags[1,1:3,1:3]}
        for name in ("IMAGE","NHITS","FLAGS"):
            start,end,positions=sample_span(by_name[name],1,1,1,2,2)
            actual=decode_sample(raw_file[start:end+1],by_name[name],positions).reshape(2,2)
            np.testing.assert_array_equal(actual,expected[name])

    def test_sample_indexing_and_axis_order(self):
        start,end,positions=sample_span(layout(),1,1,1,2,2)
        self.assertEqual(start,FITS_BLOCK+(1*12+1*4+1)*4); self.assertEqual(positions,[0,1,4,5]); self.assertGreater(end,start)

    def test_sample_bounds(self):
        with self.assertRaises(ValueError): sample_span(layout(),2,0,0,1,1)

    def test_big_endian_float_decoding_and_nan(self):
        raw=np.asarray([1.5,np.nan,3.5,4.5],dtype=">f4").tobytes()
        values=decode_sample(raw,layout(bitpix=-32,axes=(4,1,1)),[0,1,2,3])
        self.assertEqual(values[0],1.5); self.assertTrue(np.isnan(values[1]))

    def test_integer_scaling(self):
        raw=np.asarray([1,2],dtype=">i4").tobytes()
        values=decode_sample(raw,layout(bitpix=32,axes=(2,1,1),bscale=2,bzero=10),[0,1])
        np.testing.assert_array_equal(values,[12,14])

    def test_blank_becomes_nan(self):
        raw=np.asarray([-99,2],dtype=">i4").tobytes()
        values=decode_sample(raw,layout(bitpix=32,axes=(2,1,1),blank=-99),[0,1])
        self.assertTrue(np.isnan(values[0])); self.assertEqual(values[1],2)

    def test_budget_rejects_before_request(self):
        ledger=TransferLedger(max_bytes=3)
        with self.assertRaises(TransferBudgetExceeded): ledger.reserve_range(4)

    def test_range_request_limit(self):
        ledger=TransferLedger(max_range_requests=1); ledger.reserve_range(1)
        with self.assertRaises(TransferBudgetExceeded): ledger.reserve_range(1)

    def _client(self,response,total=100):
        client=BoundedRangeClient(TransferLedger(),FakeSession(response)); client.identity=ProductIdentity(response.url,total,None,None); return client

    def test_http_200_is_closed_without_body_consumption(self):
        response=FakeResponse(200,b"x"*100,{"Content-Length":"100"}); client=self._client(response)
        with self.assertRaisesRegex(RangeResponseError,"body was not consumed"): client.get(response.url,0,0)
        self.assertTrue(response.closed); self.assertEqual(client.ledger.body_bytes,0)

    def test_content_range_must_match(self):
        response=FakeResponse(206,b"x",{"Content-Range":"bytes 1-1/100","Content-Length":"1"}); client=self._client(response)
        with self.assertRaises(RangeResponseError): client.get(response.url,0,0)

    def test_truncated_range_is_rejected(self):
        response=FakeResponse(206,b"x",{"Content-Range":"bytes 0-1/100","Content-Length":"2"}); client=self._client(response)
        with self.assertRaisesRegex(RangeResponseError,"truncated"): client.get(response.url,0,1)

    def test_product_length_change_is_rejected(self):
        response=FakeResponse(206,b"x",{"Content-Range":"bytes 0-0/101","Content-Length":"1"}); client=self._client(response)
        with self.assertRaisesRegex(RangeResponseError,"identity changed"): client.get(response.url,0,0)


if __name__ == "__main__": unittest.main()
