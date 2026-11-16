# DR1.5 Pre-Retrieval Live Plan

**Experiment ID:** `CRONOSCOPE_DR1_5_NPIX7945_MULTI_2026_11_15`
**Product:** `Npix7945_cube.fits`
**Defined before new archive access:** 2026-11-15

## Fixed selections

Genuine saved SPECTRAL_CHANNELS metadata defines:

| Index | Detector/subchannel | Central wavelength | Bounds | Bandwidth |
|---:|---|---:|---:|---:|
| 0 | D1 / 1 | 0.753000021 µm | 0.742999971–0.762000024 µm | 0.017999999 µm |
| 20 | D2 / 4 | 1.195000052 µm | 1.179999948–1.210000038 µm | 0.028999999 µm |
| 100 | D6 / 16 | 4.951000214 µm | 4.929999828–4.972000122 µm | 0.037000000 µm |

Channels 51 and 52 are excluded.

Two non-overlapping, adjacent 4×4 regions are fixed:

1. zero-based `(x=90, y=107, width=4, height=4)`;
2. zero-based `(x=94, y=107, width=4, height=4)`.

The product, channels, regions, and order will not change after retrieval starts.

## Request and transfer forecast

- 1 HEAD request.
- 11 one-block FITS-header ranges.
- 1 SPECTRAL_CHANNELS table range, cached for all samples.
- 18 science ranges: 3 arrays × 3 channels × 2 regions.
- Total forecast: **31 HTTP attempts**.
- Header bytes: 31,680.
- Channel-table bytes: 2,856.
- Science bytes: 18 × 6,160 = 110,880.
- Total forecast body: **145,416 bytes**.

Limits are 40 attempts and 16 MiB. No retry is planned. All reservations are persistent and committed before I/O.

## Independent validation

After all 18 science ranges are durably saved, archive access stops. Offline code constructs one sparse logical FITS file from the genuine headers and saved ranges. Astropy independently reads each `[channel, y:y+4, x:x+4]` IMAGE/NHITS/FLAGS slice and compares exact values against the standalone decoder, with NaNs equal by position. This validates decoding/alignment, not external calibration.

## Stop rule

The FLAGS response for channel 100, region 2 is the final authorized archive request. No additional region, channel, product, or retry may be added without a new plan and authorization.
