# Experimental DR1 Cube Sample API Contract

## Endpoint

`POST /api/experimental/dr1/cube/sample`

The service binds to `127.0.0.1` by default. It is not registered in the
production Cronoscope WSGI application.

## Request

Content type must be `application/json`; the encoded body may not exceed 4096
bytes. Exactly these fields are required and no other fields are accepted:

```json
{
  "product_id": "Npix7945_cube",
  "channel": 20,
  "x": 90,
  "y": 107,
  "width": 4,
  "height": 4
}
```

All numeric fields are strict JSON integers; booleans are rejected. Channel
must be 0–101, except blank channels 51 and 52 are unavailable. Width and
height must be positive and no greater than 32. The zero-based region must be
inside the 512×512 tile.

`Npix7945_cube` is the only product identifier. URLs, filesystem paths,
experiment IDs, budgets, cache paths, and live-access controls are not request
fields.

## Success response

HTTP 200 returns classification `EXPERIMENTAL_DR1_CUBE_SAMPLE` with:

- allowlisted product, release, collection, URL, size, and archive identity;
- channel index and genuine SPECTRAL_CHANNELS metadata;
- zero-based origin and dimensions;
- aligned IMAGE, NHITS, and raw FLAGS arrays;
- dtype and finite count for every array;
- JSON `null` for nonfinite values and explicit missing counts;
- IMAGE unit and strict scientific non-claims;
- HDU sequence, header hashes, range hashes, and axis order;
- validation state, including whether the response is a public verified-result
  replay or a current raw-range decode;
- persistent server budget, cache, runtime, and peak-RSS accounting.

## Errors

Errors use classification `EXPERIMENTAL_DR1_CUBE_SAMPLE_ERROR`, `status:
ERROR`, and a stable code/message/details object. Expected codes include:

- `INVALID_REQUEST`, `UNKNOWN_PARAMETERS`, `MISSING_PARAMETERS`;
- `UNKNOWN_PRODUCT`, `INVALID_CHANNEL`, `MISSING_CHANNEL`;
- `INVALID_REGION`, `REGION_TOO_LARGE`, `REGION_OUT_OF_BOUNDS`;
- `GENUINE_EVIDENCE_UNAVAILABLE`, `UNSUPPORTED_FITS_LAYOUT`;
- `ARCHIVE_BUDGET_EXHAUSTED`, `RETRIEVAL_BUSY`, `ARCHIVE_RANGE_FAILURE`.

Tracebacks, cache paths, ledger paths, and credentials are never returned.

The default public package serves only the six recorded verified selections.
Its response sets `public_result_replay: true` and
`current_raw_range_decode_performed: false`; the recorded source-result SHA-256
is included. A valid but unrecorded selection returns
`GENUINE_EVIDENCE_UNAVAILABLE` rather than generating values. Raw response
bodies, FITS data, and request ledgers are not part of the public fixture.

## Resource contract

- One allowlisted tile and one channel per request.
- Maximum region: 32×32.
- One concurrent retrieval.
- One fixed server ledger: 40 attempts and 16 MiB total response bodies.
- Exact-range cache: SHA-256 verified, atomic, 2 MiB LRU default.
- Redirects and ranges larger than 1 MiB are forbidden in live mode.
- Complete-tile GETs are forbidden.
