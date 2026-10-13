# Contract correction and three-pass review

Date: 2026-10-12. Agent: Codex. Branch: feature/search-only-bridge.
Base examined: abc1781b0bb8c6ae74f6f780e8d1e0e3581fc607.
Scope: contract/fixtures/config only; no plugin implementation was changed. The target manifest is a contractual
fixture, to be applied by the implementer. No archive, merge or push was performed.

SB-M01: H19-H22 additions plus MODIFIED full-mode deltas, with H6 applying to both modes. SB-M02: active profile
configuration and fail-closed scope, no global fallback or search-mode MCP-token read. SB-M03: wire v1, precise
input/output/error/list schemas, origin normalization refusal and a distinct model envelope. SB-M04: both-mode
manifest fixture, conditional secrets and potential versus registered catalog. SB-M05: complete TDD/guard/state/
curl/real-profile/manual/CI/closure tasks. SB-m01: exact git archive tar bytes, full SHA, digest and size.

The three joint passes corrected historical custody language and line-envelope details (pass 1), completed
tools/list schemas and offline-install constraints (pass 2), and fixed import-cache isolation in before/after
checks (pass 3). These were contract corrections, not verification of an implemented search bridge.

## Executed validation

- `openspec validate --all --strict`: 2 passed, 0 failed (2 items), after each editing batch and pass.
- From companion foundation root:
  `python openspec/changes/harness-foundation/reports/validate-contract.py --bridge-root ../hermes-cited`:
  314 PASS across the joint contract checks, including both identical wire files, H0-H22 identifier merge,
  valid target manifest, request boundaries and all requirement scenarios. This is a report utility, not a runtime
  dependency on the companion repository.
- Shared schema SHA-256: `f09ad94cefa06df570d1c8fee681f47df9fd5ce162ea8ebb52943d1e343ceb00`.
- `git diff --cached --check`: exit 0.
- Initial `gitleaks protect --staged` found one curl-auth-header match on a synthetic bearer example in tasks.md.
  The example now reads its synthetic authorization header from a temporary file; no detector exception or
  allowlist was added. The following `gitleaks protect --staged` exited 0 with no leaks found. It is repeated
  before commit after this report is staged.

The upstream CLI and scope evidence was read at Hermes dce1e9b37581dd62e480a9064dc04a709c2940d3. It was never run
from the personal installation. The command uses --profile and --ref, not a repository@sha pseudo-argument.
The existing .github/workflows/tests.yml was inspected, not claimed as executed on an unpushed future SHA.

## Issues

- NOT DONE: implementing the approved contract, real isolated CLI/handler integration, full regression suite,
  independent implementation review, archive and distribution merge pin are the next delivery, outside this run.
- UNKNOWN: remote CI for this correction commit; no push was authorized.

Contract verdict: PASS. This is not a PASS for runtime implementation or permission to bypass the closure tasks.
