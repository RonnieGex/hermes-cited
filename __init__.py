"""Hermes Agent entry point of the hermes-cited plugin.

Hermes discovers ``plugin.yaml`` and this file in ``$HERMES_HOME/plugins/<name>/`` (or clones the
repository there with ``hermes plugins install``), imports this module as a package whose search
location is the repository root, and calls ``register(ctx)``. The module also loads when a tool
imports it as a top-level module, which is what pytest does with the root of a repository.
"""

from __future__ import annotations

if __package__:
    from .hermes_cited.plugin import register
else:
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from hermes_cited.plugin import register

__all__ = ["register"]
