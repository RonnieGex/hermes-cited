# Step 1.2 (round 2) — the fake conforms to the closed wire

- Change: `search-only-bridge` · Branch: `feature/search-only-bridge` · Agent: DeepSeek
- Date: 2026-10-12 · Python: `.venv\Scripts\python` (3.11.15) · `PYTHONDONTWRITEBYTECODE=1`
- Round 1 review item: **M04** (BROKEN, Major) — the delivered fake read and parsed the body before
  authenticating, accepted unknown envelope properties, reported a parsed `null` as a parse error, and
  echoed a non-null id for an invalid version.

## What was wrong (measured by the R1 probe)

| Entry | Expected | Real (before) |
|---|---|---|
| wrong bearer and 17000 bytes | 401 before processing the body | 413 |
| valid `tools/list` plus `extra:1` | 400, -32600, id null | 200 with catalog and id 41 |
| authenticated JSON `null` | 400, -32600, id null | 400, -32700, id null |
| jsonrpc `1.0`, id 41 | 400, -32600, id null | 400, -32600, id 41 |

## RED — the new wire-conformance module

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider tests/test_chassis_fake.py
# FAILED test_authentication_precedes_the_body_even_when_it_is_oversized
# FAILED test_an_invalid_envelope_is_32600_with_a_null_id[extra property]
# FAILED test_an_invalid_envelope_is_32600_with_a_null_id[json null]
# FAILED test_an_invalid_envelope_is_32600_with_a_null_id[missing version]
# FAILED test_an_invalid_envelope_is_32600_with_a_null_id[wrong version]
# 5 failed, 11 passed in 8.51s
# exit code 1
```

## What was changed

- `Handler.do_POST` verifies `Authorization: Bearer <token>` **before** it parses the body; a bad bearer
  is 401 `{"code":"unauthorized"}` whatever the body size, and the request is recorded with `body: null`
  to prove the body was not parsed.
- The oversized check runs after authentication, so an authenticated body over 16 KiB is 413
  `{"code":"body_too_large"}`.
- `_invalid_envelope` enforces the closed envelope: no property outside `{jsonrpc, id, method, params}`,
  `jsonrpc`, `id` and `method` required, and `jsonrpc == "2.0"`.
- A body that fails to parse is `-32700`; a body that parses to `null`, a list (batch) or a non-dict is
  `-32600` with id `null`. An invalid envelope, version or id is `-32600` with id `null`.
- The new module `tests/test_chassis_fake.py` covers authentication order, oversize, all invalid-envelope
  classes, parse error, valid `tools/list`, unknown method, unknown tool, invalid arguments, 404 and 405.

## GREEN

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider tests/test_chassis_fake.py
# ................                                                         [100%]
# 16 passed in 10.12s
# exit code 0
```

The full H21 suite and the external R1 probe agree:

```powershell
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider tests/test_search_wire.py
# 69 passed in 37.11s
.\.venv\Scripts\python -m pytest -q -p no:cacheprovider `
  C:\Users\Franc\Documents\katalis-dev\tasks\test_bridge_r1_adversarial.py -k delivered_fake_conforms
# 4 passed, 23 deselected in 2.61s
```

## Verdict

PASS. The fake is now a conforming oracle of the closed wire: authentication precedes body parsing, the
envelope is closed, `null` is an invalid request and not a parse error, and an invalid version or id
answers a null id. Delivery commit: `ee2eddb`.
