# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Assert on what a CLI *said*, not on where the renderer broke the line.

Rich soft-wraps to the terminal width, so `result.output` can contain `orp\\nhan.py` or
`function_style=sna\\nke_case`. An assertion against the raw string then passes or fails depending
on `COLUMNS`, which nothing in the test declares and CI does not hold constant.

Both occurrences found so far were in **cited proof** for a delivered contract, and both were
invisible until the cited files were run on their own — the full suite stayed green because xdist
sets a different width:

* `INT-US-05` — `test_lineage_e2e.py` failed at `COLUMNS=80`, the no-TTY default, and again at 40
  on a second assertion the first fix did not cover.
* `INT-US-25` — `test_cli_standards_integration.py` failed at `COLUMNS=60`, on the two tests that
  are the entire proof of its upsert and `.specweaverignore` claims.

Found by `TECH-017` SF-02 and SF-03.
"""

from __future__ import annotations

import re

#: SGR escapes. Stripped before comparison because Rich puts them *inside* tokens, not only around
#: them — it highlights the number in `SpecWeaver v0.1.0`, so the string carries
#: `v0.\x1b[1;36m1.0\x1b[0m` and squashing whitespace alone still misses `0.1.0`. Measured
#: 2026-08-15 across 28 tests in all three tiers (`TECH-050`).
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def shows(output: str, needle: str) -> bool:
    """Whether `needle` appears in `output`, ignoring soft wrapping.

    Both sides are whitespace-squashed, so a message broken across a line boundary still matches.
    **Presence checks only** — it destroys layout, ordering and word boundaries, so never assert
    those with it, and prefer a distinctive needle over a short one.

    Colour is stripped too. `tests/conftest.py` already pins the suite colour-free, so this is the
    second of two guards rather than the only one — but a test that deliberately re-enables colour,
    or a runner that sets `FORCE_COLOR` some future way, still gets a correct answer here.

    Squashing both sides matters: an earlier version squashed only the output, which silently failed
    for any needle containing a space.
    """
    plain = _ANSI.sub("", output)
    return "".join(needle.split()) in "".join(plain.split())
