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


def shows(output: str, needle: str) -> bool:
    """Whether `needle` appears in `output`, ignoring soft wrapping.

    Both sides are whitespace-squashed, so a message broken across a line boundary still matches.
    **Presence checks only** — it destroys layout, ordering and word boundaries, so never assert
    those with it, and prefer a distinctive needle over a short one.

    Squashing both sides matters: an earlier version squashed only the output, which silently failed
    for any needle containing a space.
    """
    return "".join(needle.split()) in "".join(output.split())
