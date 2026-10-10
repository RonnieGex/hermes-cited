# Step 5b — M-R7-2, the cross-repository document check

The local gate always runs the check of `community-hermes/docs/mcp.md`, with `CITED_DOCS_REPO`
set to the sibling checkout. This is the separate evidence of that run.

- `CITED_DOCS_REPO`: the sibling worktree of `community-hermes` (no personal path is versioned)
- exact SHA of `community-hermes` at run time: `3a636f8a006a42c4177247857180d0513f40c1bd`
- command: `pytest -q -rs tests/regressions/test_r6_docs.py tests/regressions/test_r8_docs.py`
- result: 16 passed in 0.67s

Without the variable the cross-repository assertions are skipped with the explicit reason
`CITED_DOCS_REPO is not set: the cross-repository check of community-hermes/docs/mcp.md is omitted`.
The isolated extraction of `reports/2026-10-10-step-48-standalone-r8.md` proves it.

```
................                                                         [100%]
16 passed in 0.67s
```
