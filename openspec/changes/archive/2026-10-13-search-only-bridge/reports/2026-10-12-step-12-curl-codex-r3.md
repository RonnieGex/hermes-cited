# Independent HTTP verification, round 3

Reviewer: Codex. Branch: feature/search-only-bridge. Product base: 28818e6.
This report is the task 5.1/12.6 validation evidence requested inside the change.
The new probe, complete argv and raw outputs stay outside the repository in
`bridge-codex-r3-curl.py`, `bridge-codex-r3-curl-red.log` and `bridge-codex-r3-curl-green.log`.

## Executed command and limits

```text
.venv/Scripts/python ../tasks/bridge-codex-r3-run.py bridge-codex-r3-curl-green .venv/Scripts/python.exe ../tasks/bridge-codex-r3-curl.py
```

The supervisor received the absolute Python and probe paths. It has a 900-second limit.
The probe starts `tests/fakes/chassis_surface.py --port 0 --record <temporary-log>
--workspace <temporary-directory> --token <synthetic-sentinel>` in its own process.
Each call executes the following argv, with its own request/response file and method:

```text
curl.exe --silent --show-error --max-time 10 --request POST http://127.0.0.1:57155/api/chassis/mcp --header "Content-Type: application/json" --header @<temporary-authorization-file> --output <temporary-response-file> --write-out %{http_code} --data-binary @<temporary-request-file>
```

Each curl process has an additional 15-second subprocess timeout. Authorization is read from a
temporary file, never written in this report. No provider or personal service is used.

## New cases and measured results

| Input | Expected | Before | After |
| --- | --- | --- | --- |
| Query of 1000 U+1F9ED code points, limit 8, id 37 | 200, result | PASS | PASS |
| Query of 1001 U+1F9ED code points, limit 8, id 38 | 200, -32602, id 38 | PASS | PASS |
| Negative request id -37 | 400, -32600, null id | PASS | PASS |
| tools/list with params array, id 39 | 200, -32602, id 39 | PASS | PASS |
| POST to /api/chassis/mcp?round=3 | 404 | PASS | PASS |
| PATCH to the endpoint | 405 | 501 | 405 |
| DELETE to the endpoint | 405 | 501 | 405 |
| HEAD to the endpoint | 405 | 501 | 405 |

The success result contains the fake's three passages with sequential numbers 1, 2 and 3.
The recorded 1000-code-point query is byte-preserving after JSON decoding. The request log contains
the redaction sentinel and no synthetic bearer. No response is claimed to come from the real Harness.

RED: exit 1, 4.08 seconds, three method failures. Owned PID 34204, port 51866, both closed afterwards.
GREEN: exit 0, 3.11 seconds, eight cases passed. Owned PID 21400, port 57155.
`process_stopped=true`, `port_closed=true`, `header_deleted=true`.

Before and after, the complete home inventory has exactly one regular file:
`sentinel`, SHA-256 `540ac51dc4f11de5fdd5399310c68376069a6b7a09aca034f00633721f0ddeb7`.
No cited directory is created. There is no plugin database.

## Issues

- NOT DONE: independent review of Codex's small correction and final approval by Fable.
- UNKNOWN: conformance of the real Harness service; this run verifies the delivered fake.
