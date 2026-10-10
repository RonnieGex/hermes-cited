# Step 0 — branch and regularization of the open changes (M-R3-7)

Command and result of each action of this step.

| Action | Command | Result |
|---|---|---|
| Branch | `git -C hermes-cited checkout -b feature/hermes-plugin` | `Switched to a new branch 'feature/hermes-plugin'`, from `63959cd` |
| Branch check | `git rev-parse --abbrev-ref HEAD` | `feature/hermes-plugin` |
| Archive round 1 | `git mv openspec/changes/hermes-plugin openspec/changes/archive/2026-10-10-hermes-plugin` | tracked rename, history preserved |
| Archive round 2 | `git mv openspec/changes/hermes-plugin-r2 openspec/changes/archive/2026-10-10-hermes-plugin-r2` | tracked rename, history preserved |
| Open changes after | `Get-ChildItem openspec/changes` | `hermes-plugin-r3`, `hermes-plugin-r4` (two open, the standard's maximum) |
| Round 3 | note added to `openspec/changes/hermes-plugin-r3/tasks.md` | kept open and marked **not archived**, with its 3 Blockers named, so it is never archived as approved |

`hermes-plugin-r4` carries `proposal.md`, `design.md` (D9 to D15), `specs/hermes-plugin/spec.md`
(H4, H5, H9, H10 modified; H13, H14, H15 added) and `tasks.md`, written before any code of this round.
