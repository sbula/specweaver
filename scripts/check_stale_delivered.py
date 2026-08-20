# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prose may not call a capability delivered when the matrix says it is not.

A capability's flag lives in `capability_matrix.md`, and that is the one fact. Its *claims* live
everywhere else — a story's prerequisite line, a queue candidate's Pros, a P-row's owner — and
nothing read the second kind.

Measured 2026-08-20, after six capabilities were set back from `✅` to `🔧`: twelve places still
said `✅`, the doc gate passed all twelve, and the Active Routing Queue's first candidate was a
capability that had already been built. An agent reading the queue would have rebuilt it.

Usage:
    python scripts/check_stale_delivered.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MATRIX = REPO_ROOT / "docs" / "roadmap" / "capability_matrix.md"
ROADMAP = REPO_ROOT / "docs" / "roadmap"

CAP = r"[A-E]-[A-Z]+-\d+"

#: The matrix cell: the flag, then the id. This IS the fact, so it is never a claim.
_FLAG = re.compile(rf"`(✅|🔧|🔜|🔮)\s+({CAP})`")

#: A claim: the id, then a tick. `` `D-UI-01` ✅ `` — the shape prose uses to assert delivery.
_CLAIM = re.compile(rf"`({CAP})`\s*✅")


def flags_from(text: str) -> dict[str, str]:
    """`{capability: flag}` as the matrix declares it."""
    return {cap: flag for flag, cap in _FLAG.findall(text)}


def stale_claims_in(text: str, flags: dict[str, str]) -> list[str]:
    """Capabilities this text calls delivered that the matrix does not.

    A capability the matrix has never heard of is ignored rather than failed: an id from a document
    that predates the matrix is a stale document, not a false claim, and failing on it would make
    the gate about archaeology.
    """
    return [cap for cap in _CLAIM.findall(text) if flags.get(cap, "✅") != "✅"]


def main(argv: list[str] | None = None) -> int:
    if not MATRIX.is_file():
        print(f"could not run: no capability matrix at {MATRIX}", file=sys.stderr)
        return 2

    flags = flags_from(MATRIX.read_text(encoding="utf-8"))
    if not flags:
        print("could not run: the matrix declared no capability flags", file=sys.stderr)
        return 2

    offences: list[tuple[Path, int, str]] = []
    for path in sorted(ROADMAP.rglob("*.md")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            offences += [
                (path.relative_to(REPO_ROOT), number, cap) for cap in stale_claims_in(line, flags)
            ]

    if offences:
        print(f"stale delivered claims ({len(offences)}):\n")
        for path, number, cap in offences:
            print(f"  {path}:{number}  calls {cap} ✅ — the matrix says {flags[cap]}")
        print(
            "\nThe matrix flag is the fact; prose asserting a different one is a second copy. "
            "A capability that is `🔧` is built and NOT approved, and reading it as delivered is "
            "how work gets rebuilt or closed without its sign-off."
        )
        return 1

    print(f"Stale-delivered check: {len(flags)} capability flag(s), no contradicting prose")
    return 0


if __name__ == "__main__":
    sys.exit(main())
