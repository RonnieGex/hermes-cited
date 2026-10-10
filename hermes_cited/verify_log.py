"""``python -m hermes_cited.verify_log <audit.jsonl>``: verify the chain of the cited-mode log (H5).

Exit 0 with the number of entries when the chain verifies. Exit 1 with the first broken entry
when an entry was altered, removed or reordered. Exit 2 on a usage error. The token is never
read and never printed.
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
        print("OK: {0} entries, the chain verifies.".format(count))
        return 0
    print("BROKEN: {0}".format(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
