# Experimental Cube API Contract

This is a future design only. No production route was added.

## Request

`POST /experimental/dr1/cube/region`

```json
{
  "product_url": "official explicit IRSA FITS URL",
  "product_identifier": "archive publisher ID",
  "experiment_id": "explicit persistent-ledger ID",
  "spectral_channel": 20,
  "x": 90,
  "y": 107,
  "width": 4,
  "height": 4,
  "allow_blank_channel": false
}
```

Validation rules: channel 0–101; channels 51/52 rejected unless explicitly acknowledged; positive region no larger than 32×32; region contained within the verified cube; explicit product identity and persistent budgets required.

## Response

The response mirrors the reader JSON:

- aligned IMAGE, NHITS, and FLAGS arrays;
- original dtypes, IMAGE unit, and raw FLAGS statement;
- detector/subchannel/wavelength metadata;
- pixel extent, FITS/NumPy axis order, and retained WCS header context;
- product URL, size, Last-Modified/ETag, HDU sequence, header hashes, and range hashes;
- validation classification and resource accounting;
- explicit absence of uncertainty and scientific limitations.

## Future application boundary

A future adapter should call the experimental reader behind a separate cube-specific service. It must never route cubes through the 2-D DR1 Wide/Deep normalizer or temporal comparison API. The adapter must preserve IMAGE/NHITS/FLAGS together, expose blank-channel state, retain the SQLite experiment ledger, and return fail-closed errors without substituting HiPS PNG values. Browser work requires a separately reviewed phase.
