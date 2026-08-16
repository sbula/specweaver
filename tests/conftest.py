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
from typing import TYPE_CHECKING

import pytest

from tests.baseline_snapshot import BASELINES, rewrites, snapshot

if TYPE_CHECKING:
    from collections.abc import Iterator

os.environ["NO_COLOR"] = "1"  # Rich: the CLI's own output
os.environ["PY_COLORS"] = "0"  # pytest: its terminal writer, and anything parsing it
os.environ.pop("FORCE_COLOR", None)  # inherited from an agent shell; would beat both


@pytest.fixture(autouse=True)
def _baselines_are_read_only() -> Iterator[None]:
    """No test may rewrite a gate's ratchet baseline.

    `scripts/baselines/` is the standard this repo is measured against, and nothing compares a
    baseline against what it was — so a test that writes one relaxes or corrupts a gate inside a
    diff that reads as ordinary test work.

    Found for real on 2026-08-16: `test_mutation_seam.py` called `mutation.main()` without
    `--ledger`, and `record_run` appended to the **real** `mutation_findings.json` on every suite
    run, inventing a finding for a mutant that existed only inside a fixture. It was noticed by an
    unexplained modification in `git status`, which is not a detection mechanism.

    Fails the offending test rather than restoring the file: a fixture that silently rewrote
    version-controlled content would be doing the very thing it exists to catch. Nothing cascades —
    the next test's "before" is the polluted state, so only the writer fails.
    """
    before = snapshot(BASELINES)
    yield
    changed = rewrites(before, snapshot(BASELINES))
    if changed:
        pytest.fail(
            "this test wrote to scripts/baselines/, which is version-controlled gate state:\n  "
            + "\n  ".join(changed)
            + "\nPoint the tool at tmp_path instead — most take a --ledger/--baseline argument.",
            pytrace=False,
        )
