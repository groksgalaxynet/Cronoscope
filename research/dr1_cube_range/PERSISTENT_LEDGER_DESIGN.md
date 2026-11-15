# Persistent Ledger Design

## Safety model

`persistent_ledger.py` uses SQLite transactions with `BEGIN IMMEDIATE`, foreign keys, WAL journaling, a 10-second busy timeout, and `synchronous=FULL`. An experiment ID must be explicitly initialized. Opening a missing, corrupt, unknown, schema-incompatible, or semantically inconsistent ledger fails closed.

Every HEAD or range attempt is reserved and committed before the HTTP client is called. The transaction increments the shared attempt count, inserts a request row, and charges the planned maximum response body. Concurrent processes serialize at this transaction, so they cannot independently observe and spend the same remaining budget.

## Byte semantics

Two counters are intentionally retained:

- `actual_received_bytes`: chunks durably recorded as the client receives them.
- `charged_bytes`: the safety budget, charged to the full planned body before I/O and never refunded.

A completed exact range normally has equal actual and charged bytes. A timeout, truncated response, disconnect, explicit interruption, or crash can have fewer observed bytes than charged bytes. The full planned charge remains, preventing interruption or restart from creating new budget. If a peer sends more bytes than declared, the observed overage is committed to both actual and charged accounting before the request fails; subsequent budget is exhausted or negative rather than silently undercounted.

There is an unavoidable final-chunk crash window between the operating system receiving bytes and Python committing the chunk. Precharging the entire planned response is the conservative bound for that case. The ledger never claims that `actual_received_bytes` is exact after an uncatchable process/host failure; `charged_bytes` is the enforceable no-undercount safety figure.

## Request states

- `reserved`: committed before network I/O; also the durable representation of a crash after reservation.
- `completed`: exact bounded response validated and consumed.
- `failed`: caught transport, status, range, identity, length, decoding, or accounting error.
- `interrupted`: explicit interruption recorded by the caller.
- `rejected`: terminal state available for callers that reserved an attempt but rejected it before body processing.

Retries call `reserve_request` again and receive a new sequence number. A request denied before reservation because no shared budget remains is not an HTTP attempt and does not create a request row.

## Integrity checks

Every open/snapshot validates SQLite `quick_check`, schema version, experiment existence, allowed request states, and equality between experiment counters and recomputed request-row totals. Reinitializing an existing experiment ID fails and preserves its history. A new experiment ID requires an explicit initialization transaction.

## Command-line behavior

The range utility now requires `--ledger-db` and `--experiment-id`. `--initialize-ledger` is explicit; `--initialize-only` creates or inspects state without network activity. Before any experiment request, the complete snapshot—including remaining attempts and remaining charged bytes—is printed and flushed. The legacy in-memory recovery entry point is retired and raises without issuing a request.

## Scope

This is isolated research code. It does not authorize archive access, production cube support, retries, deployment, or DR1.4.
