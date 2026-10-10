"""Permanent regressions of the seventh review M-R7-2: the cross-repository check is explicit.

The suite of this repository must run green in an isolated checkout. The check of
``community-hermes/docs/mcp.md`` runs only when ``CITED_DOCS_REPO`` names a checkout; without that variable
it is skipped with an explicit reason instead of failing or passing in silence. The local gate of the
repository always sets the variable, records the exact SHA of ``community-hermes`` and leaves its evidence
in a separate report; the CI workflow declares the omission because it checks out one repository only.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DOCS_MODULE = REPO / "tests" / "regressions" / "test_r6_docs.py"


def docs_module():
    """The document module, loaded fresh so it reads ``CITED_DOCS_REPO`` at call time."""
    spec = importlib.util.spec_from_file_location("round8_docs_module", DOCS_MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m_r7_2_without_the_variable_the_cross_repo_check_is_omitted(monkeypatch):
    monkeypatch.delenv("CITED_DOCS_REPO", raising=False)
    module = docs_module()
    assert module.docs_repo() is None
    assert module.community_documents() is None
    assert module.OMITTED_REASON.strip(), "the omission must carry an explicit reason"


def test_m_r7_2_with_the_variable_the_check_points_at_that_checkout(monkeypatch, tmp_path):
    monkeypatch.setenv("CITED_DOCS_REPO", str(tmp_path))
    module = docs_module()
    assert module.docs_repo() == tmp_path
    assert module.community_documents() == tmp_path / "docs" / "mcp.md"


def test_m_r7_2_the_workflow_declares_the_omission():
    text = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    flat = " ".join(text.split())
    assert "CITED_DOCS_REPO" in flat
    assert "omitted" in flat.lower() or "omite" in flat.lower()
