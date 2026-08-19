# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Put the operational rules in front of an agent before it can make the mistakes they prevent.

`CLAUDE.md` is loaded automatically and points at `docs/dev_guides/working_in_this_repo.md`, but a
pointer relies on the agent choosing to follow it — and the agent most likely to skip it is the one
that needs it. This surfaces the short version unconditionally, and surfaces the handover when one
exists, since that file is gitignored and nothing else announces it.

Never blocks. A session that cannot start because its briefing failed is worse than an unbriefed one.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
GUIDE = "docs/dev_guides/working_in_this_repo.md"
HANDOVER = REPO / ".tmp" / "HANDOVER.md"

BRIEF = f"""
── SpecWeaver: read before your first change ──────────────────────────────────

  {GUIDE}
  Ten operational traps, each one an incident that cost a session.

  The four that cost the most:

  1. `$?` after a pipe is `tail`'s, not the gate's. Two commits landed on a red
     gate this way.  ->  `... | tail -3; s=${{PIPESTATUS[0]}}`
  2. Put an ABSOLUTE .venv/bin on PATH: `export PATH="$PWD/.venv/bin:$PATH"`.
     A relative entry breaks when a test chdirs — 45 phantom failures chased.
  3. Break your own guard and watch it fail. A test that cannot fail is
     decoration, and this repo keeps finding them.
  4. When a measurement surprises you, suspect the instrument first.

  Integration is implicit in the (sub)story and there is no integration story.
  Never mint an INT-US. A path one feature cannot walk is a seam FR of the
  story, its test written RED first — xfail(strict=True) naming the blocker
  while a related story is unbuilt. See ADR-005.
"""


def _leave_trace() -> None:
    """Record that the briefing ran, so it can be verified after the banner scrolls away.

    `.tmp/` is gitignored, so this never leaves the machine. Best-effort: a trace that cannot be
    written is not a reason to fail a session.
    """
    try:
        from datetime import UTC, datetime

        trace = REPO / ".tmp" / "session_brief_last.txt"
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text(datetime.now(UTC).isoformat() + "\n", encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    try:
        _leave_trace()
        out = [BRIEF]
        if HANDOVER.is_file():
            out.append(
                "  A HANDOVER IS WAITING: .tmp/HANDOVER.md — read it before `git log`.\n"
                "  It is gitignored, so it exists only on this machine.\n"
            )
        out.append("─" * 79 + "\n")
        sys.stdout.write("".join(out))
    except Exception:  # never let a briefing stop a session
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
