# SPHEREx DR1 Compatibility Note

**Prepared:** 2026-11-14  
**Scope:** architecture review only. No DR1 file was downloaded and no QR2/QR3
pipeline, release guard, scientific baseline, or cached product was changed.

## Findings

- DR1 reprocesses Survey 1 and Survey 2 spectral images. IRSA intends DR1 and
  QR3 to form the uniformly processed current spectral-image set; this must not
  be treated as a claim that DR1 equals QR3.
- The existing architecture separates retrieval, FITS normalization, WCS and
  WCS-WAVE interpretation, comparison, and UI provenance. That separation can
  accommodate a new release token after a dedicated discovery/retrieval adapter
  and release-aware fixtures are added.
- IRSA identifies three DR1 SIA2 collections: `spherex_dr1` (Wide Survey
  spectral-image MEFs), `spherex_dr1_deep` (Deep Survey spectral-image MEFs),
  and `spherex_dr1_cube` (All-Sky Cube FITS). QR3 remains separate:
  `spherex_qr3` and `spherex_qr3_deep`.
- The 102-channel All-Sky Cube is a distinct cube product, not a drop-in
  replacement for an existing image-MEF reader. It needs a separate reader,
  data-model contract, WCS validation, memory/tiling strategy, display rules,
  and citation path before any UI exposure.

## Required future validation before integration

1. Add fixed public DR1 Wide and Deep discovery fixtures and assert collection,
   release, detector, time, units, quality arrays, celestial WCS, and WCS-WAVE
   contracts.
2. Add cross-release guard tests that keep QR2, DR1, and QR3 comparisons
   explicit and prohibit unlabelled combinations.
3. Add cube-only tests for dimensionality, 102-channel metadata, WCS axes,
   subset extraction, memory bounds, and provenance. Do not route cube files
   through the image-MEF path.
4. Add current citations: Spectral Images DOI `10.26131/IRSA678`; All-Sky Cube
   DOI `10.26131/IRSA679`; required SPHEREx acknowledgement.

## Sources

- [DR1 overview](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html)
- [IRSA SPHEREx Data Access](https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-access/)
- [IRSA SPHEREx Data Releases](https://irsa.ipac.caltech.edu/spherex-archive-documentation/spherex-data-releases/)
