# Step 15 — the permanent regressions of the four reviews

Command:

```powershell
hermes-cited\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider tests/regressions
```

Result:

```text
339 passed in 123.88s
```

The directory holds one test per attack, with the review and the finding id in the docstring:

| File | Reviews | Tests |
|---|---|---:|
| `tests/regressions/test_r1_regressions.py` | round 1 (`tasks/revision-codex-hermes-cited.md`): B1-B3, M1-M7, m1 | 45 |
| `tests/regressions/test_r2_regressions.py` | round 2 (`-r2`): B-R2-1..3, M-R2-1..5, m-R2-1 | 51 |
| `tests/regressions/test_r3_regressions.py` | round 3 (`-r3`): B-R3-1..3, M-R3-1..7, m-R3-1..2 and the 31-case matrix | 139 |
| `tests/regressions/test_r4_transformer.py` | round 4 (`-r4`): B-R4-1, B-R4-2, M-R4-3, M-R4-5 | 10 |
| `tests/regressions/test_r4_record.py` | round 4 M-R4-1 (the five stages of the append) | 8 |
| `tests/regressions/test_r4_delivery.py` | round 4 M-R4-2 | 5 |
| `tests/regressions/test_r4_render.py` | round 4 M-R4-4 | 7 |
| `tests/regressions/test_r4_gate.py` | round 4 M-R4-7 | 7 |
| `tests/regressions/test_r4_matrix.py` | round 4 appendix (the 62 data variants of the extractive matrix) | 62 |
| `tests/regressions/test_r4_host.py` | round 4 through the real loader, dispatcher and finalizer: M-R4-6, B-R4-1, M-R4-2 | 5 |
| | | **339** |

The suite uses the temporary `HERMES_HOME` fixtures of `tests/conftest.py`; the host fixtures reuse the
isolated fixture of `tests/test_host.py` and skip when the read-only copy of the host is not present. No test
touches `%LOCALAPPDATA%\hermes`, the port 3240 or any live service.

The gate runs the whole directory twice: once through the full `pytest -q` claim (`H8`) and once through the
adversarial subset claim (`D8`), so a closed attack that reopens turns the gate red.
