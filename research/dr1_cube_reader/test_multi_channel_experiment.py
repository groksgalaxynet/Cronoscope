from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from research.dr1_cube_reader.multi_channel_experiment import (
    CHANNELS, REGIONS, _array, _sha256_file,
)


class MultiChannelPlanTests(unittest.TestCase):
    def test_fixed_plan_is_within_authorized_limits(self):
        self.assertEqual(CHANNELS,(0,20,100))
        self.assertTrue(set(CHANNELS).isdisjoint({51,52}))
        self.assertEqual(len(REGIONS),2)
        self.assertTrue(all(width<=16 and height<=16 for _,_,width,height in REGIONS))
        self.assertEqual(1+11+1+(3*len(CHANNELS)*len(REGIONS)),31)

    def test_json_nulls_restore_to_float_nan(self):
        values=_array([[1.0,None]],">f4")
        self.assertEqual(values[0,0],1.0); self.assertTrue(np.isnan(values[0,1]))

    def test_sparse_hashing_is_streamed_and_exact(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"artifact"; path.write_bytes(b"abc")
            self.assertEqual(_sha256_file(path),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


if __name__=="__main__": unittest.main()
