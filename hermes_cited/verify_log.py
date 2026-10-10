"""``python -m hermes_cited.verify_log <audit.jsonl>``: verify the chain of the cited-mode log (H5, D9).

Exit 0 with the number of entries when the chain is internally consistent. Exit 1 with the first broken
entry when an entry was altered, removed from the middle, reordered or when an entry does not carry the
schema. A complete suffix cut or a whole file rewritten with every hash recomputed stays internally
consistent and this command does not detect it, so it promises nothing about either. Exit 2 on a usage
error.

What this checks is **internal consistency**: every entry, every link and every hash of the chain. It is
not a custody check: whoever can rewrite the file can also recompute the chain, and the plugin does not
pretend otherwise. Audited custody lives on the server side, with Cited Ledger. The bearer of Cited is
never read and never printed.

Run it from the installed plugin directory, which is where the module is importable:

    Push-Location (Join-Path $env:HERMES_HOME 'plugins/hermes-cited')
    try { python -m hermes_cited.verify_log (Join-Path $env:HERMES_HOME 'cited/audit.jsonl') }
    finally { Pop-Location }
"""

from __future__ import annotations

import sys

from .audit import verify_file


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: python -m hermes_cited.verify_log <audit.jsonl>")
        return 2
    count, error = verify_file(arguments[0])
    if error is None:
        print(
            "OK: {0} entries, the chain is internally consistent (this is not a custody check; see the "
            "README).".format(count)
        )
        return 0
    print("BROKEN: {0}".format(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
