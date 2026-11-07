# Preview connectivity notes (sanitized)

## Observed
- Tools curling `http://127.0.0.1:18765/` often returned 200 while a browser session reported root `ERR_CONNECTION_REFUSED` (and at least one run had a working `/api/health` narrative alongside a refused root navigation).
- On this box, `localhost` resolves with **::1 before 127.0.0.1**. The preview server initially listened only on IPv4 `127.0.0.1`.

## Mitigation applied
- Dual-bind preview (and live_bridge) to **127.0.0.1 and ::1** (not `0.0.0.0`).
- After mitigation, curl checks for `127.0.0.1`, `localhost`, and `[::1]` returned HTTP 200 for `/`.

## Caveat (do not over-claim)
**IPv6/`localhost` mismatch is a plausible explanation and was fixed prophylactically; it is not proven as the sole root cause of every browser `ERR_CONNECTION_REFUSED` (including any failures already targeting `127.0.0.1`).** Visual review remains pending; no screenshot in this pack asserts a fixed Chrome session.
