"""``python -m hermes_cited.verify_log <audit.jsonl>``: verify the chain of the cited-mode log (H5).

Exit 0 with the number of entries when the chain and its authenticated checkpoint verify. Exit 1
with the first broken entry when an entry was altered, removed, reordered or cut from the end, when
the chain was rewritten and recomputed without the key, or when the log no longer matches its
checkpoint. Exit 2 on a usage error. The key of the checkpoint is read from
``%APPDATA%\\Katalis\\hermes-cited\\audit.key`` or from ``CITED_AUDIT_KEY_PATH``. The bearer of
Cited is never read and never printed.

Run it from the installed plugin directory, which is where the module is importable:

    Push-Location (Join-Path $env:HERMES_HOME 'plugins/hermes-cited')
    try { python -m hermes_cited.verify_log (Join-Path $env:HERMES_HOME 'cited/audit.jsonl') }
    finally { Pop-Location }
"""

from __future__ import annotations

import sys

from .audit import KEY_ENV, key_path, verify_file


def main(argv=None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        print("usage: python -m hermes_cited.verify_log <audit.jsonl>")
        return 2
    count, error = verify_file(arguments[0])
    if error is None:
        print("OK: {0} entries, the chain and its checkpoint verify.".format(count))
        return 0
    hint = ""
    if "checkpoint" in error or "key" in error:
        try:
            hint = " (key: {0}, from {1})".format(key_path(), KEY_ENV)
        except Exception:
            hint = ""
    print("BROKEN: {0}{1}".format(error, hint))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
