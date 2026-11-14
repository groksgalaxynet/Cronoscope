# NASA target FITS inventory

Validation date: 2026-10-29. This inventory covers the eight original files in `nasa_targets/`; their SHA-256 values were recorded before and after analysis. No FITS file was modified.

| Target | Archive identifier / file | UTC observation time (MJD) | Band | Pixel scale | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| R Draconis | 2025W17_4B_0021_1D3 | 2025-04-24 21:06:38.391 (60789.880277) | D3, 1.6301–2.4346 µm | 6.1547 arcsec/pixel | `7c84e67b6533e40942cdec0b336910a615adf970331866098aa7748f02d343ca` |
| R Draconis | 2026W19_1A_0762_3D3 | 2026-05-06 01:12:31.213 (61166.051027) | D3, 1.6301–2.4346 µm | 6.1547 arcsec/pixel | `5b3d56a8540781ed70820fa5921a16b18519cd6960f1094a52efed519c770081` |
| Barnard's Star | 2025W33_2C_0321_1D3 | 2025-08-15 20:45:11.338 (60902.865381) | D3, 1.6301–2.4346 µm | 6.1549 arcsec/pixel | `65c173023c9623dd9872579c0cc6164beee4bcc93bb86a743a1a4e79b7692842` |
| Barnard's Star | 2026W19_1A_0403_1D3 | 2026-05-05 01:59:28.744 (61165.083638) | D3, 1.6301–2.4346 µm | 6.1543 arcsec/pixel | `e6ad64a00d6a72797e64f2e2f69aab4783b3458abfc35578e309b455f96de20a` |
| RW Aur | 2025W37_2A_0051_1D3 | 2025-09-11 16:15:33.968 (60929.678143) | D3, 1.6301–2.4346 µm | 6.1547 arcsec/pixel | `e0757d29566ade4d2b784c4cd88842d1e252ca1e513eb7017ac7e05b2a2fdcda` |
| RW Aur | 2026W10_1A_0120_1D3 | 2026-03-02 13:31:14.591 (61101.564030) | D3, 1.6301–2.4346 µm | 6.1542 arcsec/pixel | `13bf53c58fb733a9ca2c00c90bc1674d66f79fc1e1a62beb5d85df9c89eb7813` |
| WISE 0855 | 2025W19_1B_0116_1D6 | 2025-05-05 16:48:02.459 (60800.700695) | D6, 4.4115–5.0096 µm | 6.1489 arcsec/pixel | `e45a557e8084e39a3022628e6351836a5b7e4f436493beb83c52b3fcfa60d710` |
| WISE 0855 | 2026W20_1A_0033_1D6 | 2026-05-11 02:18:44.662 (61171.097016) | D6, 4.4115–5.0096 µm | 6.1605 arcsec/pixel | `3ccc391fc37f5d950796f4c897bffe65ece12adfc14c8672dc3465a1d3bdec22` |

Every file passed Astropy FITS verification and contains the same seven HDUs: primary, `IMAGE` (18 × 18), `FLAGS`, `VARIANCE`, `ZODI`, `PSF`, and `WCS-WAVE`. The science image unit is `MJy / sr`. Each `IMAGE` has a valid celestial WCS round trip. The `VERSION` header is absent; the filenames carry the `l2b-v20` (2025) or `l2b-v24` (2026) processing token.

The durable machine-readable record is [`analysis_evidence.json`](nasa_targets/analysis_evidence.json). Regenerate it and the derived previews with:

```bash
MPLCONFIGDIR=/tmp/cronoscope_matplotlib PYTHONPATH=. ./.venv/bin/python nasa_targets/analyze_targets.py
```
