# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Suite-wide invariants that must hold before anything imports a renderer.

## The suite runs colour-free

Measured 2026-08-15: with `FORCE_COLOR` set — which is how every agent-driven run sees the suite —
**28 tests across all three tiers failed**, and with it unset, none did. Same tree, same commit, one
environment variable.

The escapes land *inside* tokens, not merely around them: Rich highlights the number in
`SpecWeaver v0.1.0`, so the string becomes `v0.\\x1b[1;36m1.0\\x1b[0m` and even a
whitespace-tolerant check misses it. That made "no accepted deltas" unfollowable under an agent:
28 failures always present and never anyone's fault, which is precisely the state that rule exists
to prevent.

**Two consumers, two variables, and confusing them is why the first attempt at this fixed one test
out of 28.** `PY_COLORS` is pytest's own convention, checked first in its `should_do_markup`; Rich
has never heard of it and reads `NO_COLOR` / `FORCE_COLOR` (`rich/console.py:734,970`). The 28
failures are Rich rendering the *CLI's* output, so `NO_COLOR` is the one that matters — and
`FORCE_COLOR` must be cleared too, since an inherited one would otherwise still win.

Set at import time rather than in a fixture because Rich reads the environment when a `Console` is
constructed, and some are built at module import — a fixture would run too late.

**This protects tests nobody has written yet**, which `tests/rendering.py::shows()` cannot: that
helper only guards assertions whose author remembered to use it. Both exist deliberately, the same
belt-and-braces `scripts/_mutate.py` uses, because one guard is one environment variable away from
failing.

A test that genuinely wants colour sets it back for its own duration — see
`tests/unit/interfaces/cli/test_cli_renders_colour.py`.
"""

from __future__ import annotations

import os

os.environ["NO_COLOR"] = "1"  # Rich: the CLI's own output
os.environ["PY_COLORS"] = "0"  # pytest: its terminal writer, and anything parsing it
os.environ.pop("FORCE_COLOR", None)  # inherited from an agent shell; would beat both
