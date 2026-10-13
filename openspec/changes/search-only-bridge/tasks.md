# Tasks: search-only-bridge

Branch: `feature/search-only-bridge` from `main` at `c0f7e97`. Every run uses a temporary `HERMES_HOME`; the
installation under `%LOCALAPPDATA%\hermes` and the checkout `hermes-agent` are read-only. Secret scan before each
commit (`gitleaks protect --staged`).

## 0. Branch

- [x] 0.1 `git switch -C feature/search-only-bridge main` at `c0f7e97`. Evidence: `reports/2026-10-12-step-0-branch.md`.

## 1. Tests first (red)

- [ ] 1.1 `tests/fakes/chassis_surface.py`: a loopback HTTP fake of `POST /api/chassis/mcp` (D3) that records every
      request with its headers and can answer a redirect to another host.
- [ ] 1.2 `tests/test_search_only_mode.py`: every scenario of H12 to H14 (absent means full; unknown value refuses;
      exactly one tool; no audit record; request shape and token; the MCP token is never read; missing token named;
      redirect refused).
- [ ] 1.3 `tests/test_readme.py` extended for H15 (section present in both READMEs, same variables, same install
      command).
- [ ] 1.4 Run 1.2 and 1.3 against `main`: they fail for the right reasons. Report `reports/<date>-step-1-red.md`.

## 2. Implementation

- [ ] 2.1 `config.py`: `bridge_tools_of`, `Settings.mode`, `Settings.search_token`, `settings_from_env` by mode.
- [ ] 2.2 `client.py`: endpoint path by mode; bearer by mode; host and redirect rules unchanged.
- [ ] 2.3 `plugin.py`: `_register_search_only(ctx)`; `register(ctx)` branches once.
- [ ] 2.4 `plugin.yaml`: version `0.2.0`.

## 3. Existing tests

- [ ] 3.1 The `full` mode suite runs unchanged and green; list any test touched and why.

## 4. Run the tests

- [ ] 4.1 `pytest -q` whole suite with counts and runtime; `python -m hermes_cited` smoke if it exists.

## 5. Manual verification

- [ ] 5.1 With a temporary `HERMES_HOME`, `CITED_BRIDGE_TOOLS=search`, `CITED_URL=http://127.0.0.1:<free port>` and the
      fake surface running: call `cited_search` through the plugin's handler; paste the fake's recorded request and
      the tool's output; prove that `$HERMES_HOME/cited/` holds no file.

## 6. Documentation

- [ ] 6.1 `README.md` and `README.es.md`: the `search` mode section with the two variables, the surface, what is not
      registered, and `hermes plugins install RonnieGex/hermes-cited@<commit> --enable`.
- [ ] 6.2 `openspec/config.yaml`: the mode joins the context.

## 7. Closing

- [ ] 7.1 `/verify` against this spec; adversarial review by Codex; Blockers and Majors resolved.
- [ ] 7.2 CI green on the delivering commit; `/archive` with the explicit OK of Franc; push to `main` through the
      repository's own rules; record the archived commit and the tarball SHA-256 for `bridge.lock` of
      `harness-foundation`.
