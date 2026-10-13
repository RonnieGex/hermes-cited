"""Where an OpenSpec change lives: `openspec/changes/<name>` while open, `openspec/changes/archive/<date>-<name>`
once archived. The normative fixtures of a change (wire schema, manifest, vectors) stay inside its folder, so the
tests resolve the folder instead of hard-coding the open path."""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def change_dir(name: str) -> Path:
    changes = REPO / "openspec" / "changes"
    if (changes / name).is_dir():
        return changes / name
    archived = sorted(changes.glob(f"archive/*-{name}"))
    if not archived:
        raise FileNotFoundError(f"the change {name} is neither open nor archived under {changes}")
    return archived[-1]
