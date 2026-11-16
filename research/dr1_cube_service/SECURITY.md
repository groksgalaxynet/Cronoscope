# Security Boundary

- Only the opaque identifier `Npix7945_cube` resolves to a remote product.
- The exact server-owned URL must use HTTPS and the approved IRSA host.
- Redirect following is disabled; a redirect fails the request.
- Clients cannot provide URLs, paths, ledger IDs, budgets, cache locations,
  live-access flags, or concurrency settings.
- Request bodies are limited to 4096 bytes and unknown fields fail closed.
- The service exposes no reset endpoint and never silently creates a new
  experiment after exhaustion.
- One bounded semaphore controls all archive retrieval activity.
- Cache names are SHA-256 identities derived from the fixed product and exact
  range. Writes are atomic and reads revalidate length, identity, and hash.
- CORS is not enabled. Responses disable browser caching and MIME sniffing.
- Errors are structured and do not expose tracebacks or private paths.
- The command binds only to `127.0.0.1`; no public deployment is authorized.
- Live access is disabled by default and requires an explicit server startup
  option. DR1.6 acceptance did not enable it and made zero archive requests.

The service has no authentication because it is a localhost research process.
Any future network exposure requires authentication, TLS termination, process
isolation, operational rate limiting, audit retention, and a fresh review.
