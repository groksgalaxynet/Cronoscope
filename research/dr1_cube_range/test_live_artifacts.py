from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from astropy.io import fits

from research.dr1_cube_range.persistent_ledger import PersistentLedger
from research.dr1_cube_range.range_cube import (
    BoundedRangeClient,
    FITS_BLOCK,
    ProductIdentity,
    read_header,
)


class Response:
    def __init__(self, status, body=b"", headers=None):
        self.status_code=status; self.body=body; self.headers=headers or {}
        self.url="http://local/cube.fits"; self.history=[]; self.closed=False
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)
    def iter_content(self, chunk_size):
        if self.body: yield self.body
    def close(self): self.closed=True


class Session:
    def __init__(self, head_response=None, get_response=None):
        self.head_response=head_response; self.get_response=get_response
    def head(self, *_args, **_kwargs): return self.head_response
    def get(self, *_args, **_kwargs): return self.get_response


class RecordingByteClient:
    def __init__(self, raw):
        self.raw=raw; self.calls=[]
        self.identity=ProductIdentity("http://local/cube.fits",len(raw),None,None)
    def get(self, _url, start, end):
        self.calls.append((start,end)); return self.raw[start:end+1]


class LiveArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(); self.root=Path(self.temporary.name)
        self.ledger=PersistentLedger.initialize(self.root/"ledger.sqlite3","live-fixture",max_requests=20,max_bytes=10000)
        self.artifacts=self.root/"artifacts"
    def tearDown(self): self.temporary.cleanup()

    def test_head_identity_is_persisted_before_completion(self):
        response=Response(200,headers={"Content-Length":"100","Accept-Ranges":"bytes","Last-Modified":"fixed"})
        client=BoundedRangeClient(self.ledger,Session(head_response=response),artifact_dir=self.artifacts)
        identity=client.head(response.url)
        saved=json.loads((self.artifacts/"request_001_HEAD.json").read_text())
        self.assertEqual(identity.content_length,100); self.assertEqual(saved["last_modified"],"fixed")
        self.assertEqual(self.ledger.snapshot()["requests"][0]["state"],"completed")

    def test_range_bytes_and_metadata_are_durably_persisted(self):
        body=b"abcd"
        response=Response(206,body,{"Content-Range":"bytes 10-13/100","Content-Length":"4"})
        client=BoundedRangeClient(self.ledger,Session(get_response=response),artifact_dir=self.artifacts)
        client.identity=ProductIdentity(response.url,100,None,None)
        self.assertEqual(client.get(response.url,10,13),body)
        binary=self.artifacts/"request_001_bytes_10_13.bin"
        metadata=json.loads((self.artifacts/"request_001_bytes_10_13.json").read_text())
        self.assertEqual(binary.read_bytes(),body)
        self.assertEqual(metadata["sha256"],hashlib.sha256(body).hexdigest())

    def test_header_reader_never_requests_past_first_block_when_end_is_present(self):
        header=fits.Header({"SIMPLE":True,"BITPIX":8,"NAXIS":0}).tostring(endcard=True,padding=True).encode("ascii")
        raw=header+b"science bytes must not be touched"+b" "*FITS_BLOCK
        client=RecordingByteClient(raw)
        parsed,length,_=read_header(client,client.identity.final_url,0)
        self.assertTrue(parsed["SIMPLE"]); self.assertEqual(length,FITS_BLOCK)
        self.assertEqual(client.calls,[(0,FITS_BLOCK-1)])


if __name__ == "__main__": unittest.main()
