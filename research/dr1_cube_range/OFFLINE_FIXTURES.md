# Offline Fixture Descriptions

All DR1.3R tests are deterministic and offline. No fixture contacts IRSA or any other external host.

## HTTP fixtures

In-process response/session doubles emulate streamed HTTP behavior for:

- exact HTTP 206 range success;
- HTTP 200 full-body rejection before iteration;
- wrong `Content-Range`;
- truncated body;
- body larger than the declared/requested range;
- persistent response-byte exhaustion.

They exercise the same `BoundedRangeClient` used by the research utility. URLs use the non-routable fixture label `http://local/...`; the session double never opens a socket.

## Process and ledger fixtures

Temporary SQLite databases test reopen/restart behavior, request 20 acceptance and request 21 rejection, retry accounting, explicit interruption, `os._exit` immediately after reservation, six-process contention, missing files, random-byte corruption, semantic counter corruption, duplicate initialization, explicit new experiment IDs, and failed initialization preserving prior bytes.

## FITS fixtures

Astropy creates an in-memory six-HDU FITS file with PRIMARY, IMAGE, NHITS, FLAGS, SPECTRAL_CHANNELS, and WCS-WAVE. Tests compare the standalone byte-span decoder against Astropy for an aligned three-array sample. Additional fixtures cover 2,880-byte padding, `END` parsing, offset chaining, axis/channel/pixel order, big-endian float32/int32, scaling, BLANK-to-NaN conversion, and NaN preservation.

These FITS values are synthetic software-test data. They are not SPHEREx measurements and are not presented as genuine scientific evidence.
