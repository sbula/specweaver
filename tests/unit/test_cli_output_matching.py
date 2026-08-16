# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a CLI said, independent of how the renderer dressed it.

Proves: TECH-050 FR-1, FR-2

Two things break a raw `in` check against Rich output, and they break it differently.

**Width.** Rich soft-wraps at `COLUMNS`, so `orphan.py` arrives as `orp\\nhan.py`. `shows()` has
squashed whitespace since `TECH-017` found that twice in the cited proof of a delivered contract.

**Colour.** Escapes land *inside* tokens, not just around them: Rich highlights the number in
`SpecWeaver v0.1.0` and the string becomes `v0.\\x1b[1;36m1.0\\x1b[0m`, so even a
whitespace-squashing check fails. Measured 2026-08-15: 28 tests across all three tiers fail this
way whenever `FORCE_COLOR` is set — which is how every agent-driven run sees the suite.

The suite is therefore pinned colour-free in `tests/conftest.py`, and `shows()` strips escapes
anyway. Belt and braces, exactly as `scripts/_mutate.py` does: one guard is one environment
variable away from failing.
"""

from __future__ import annotations

import os
import re

from tests.rendering import shows

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class TestShows:
    """`shows` — presence, whatever the renderer did to the string."""

    def test_a_plain_match(self) -> None:
        assert shows("orphan.py is untagged", "orphan.py")

    def test_a_soft_wrapped_match(self) -> None:
        """[Boundary] The width failure `TECH-017` found twice in cited proof."""
        assert shows("orp\nhan.py is untagged", "orphan.py")

    def test_a_needle_containing_spaces(self) -> None:
        assert shows("Error:  Unsupported   MCP Target", "Error: Unsupported MCP Target")

    def test_colour_around_a_word(self) -> None:
        assert shows("\x1b[31mError:\x1b[0m Unsupported", "Error: Unsupported")

    def test_colour_inside_a_token(self) -> None:
        """The shape whitespace-squashing alone cannot survive.

        Rich highlights the number, so the escape lands mid-token and splits `0.1.0` in two. This
        is the failure that put 28 tests red under every agent-driven run.
        """
        assert shows("SpecWeaver v0.\x1b[1;36m1.0\x1b[0m\n", "0.1.0")

    def test_absence_is_still_absence(self) -> None:
        """[Hostile] A tolerant matcher that matches everything proves nothing."""
        assert not shows("\x1b[31mError:\x1b[0m Unsupported", "Supported MCP Target")

    def test_it_does_not_match_across_unrelated_content(self) -> None:
        assert not shows("alpha beta", "alphabetagamma")


class TestShowsIsNotTheOnlyGuard:
    """`FR-2` — the suite renders colour-free no matter what the ambient shell wants.

    `shows` only helps assertions whose author remembered to use it. This half protects the rest,
    including every CLI test written from now on.
    """

    def test_rich_is_told_not_to_colour(self) -> None:
        """`NO_COLOR` is the one Rich reads — `PY_COLORS` is pytest's and Rich ignores it.

        Confusing the two is why the first attempt at this fixed one test out of 28: it silenced
        pytest's own writer while the CLI kept emitting escapes.
        """
        assert os.environ.get("NO_COLOR") == "1"
        assert os.environ.get("FORCE_COLOR") is None

    def test_pytests_own_writer_is_also_plain(self) -> None:
        """Set in `tests/conftest.py`, so a test written tomorrow inherits it without knowing.

        This is the half that protects tests nobody has written yet. `shows()` only helps the
        assertions whose author remembered to use it.
        """
        assert os.environ.get("PY_COLORS") == "0"

    def test_rich_agrees_that_markup_is_off(self) -> None:
        """Asking Rich rather than asserting our own env var back at ourselves.

        `PY_COLORS` is the first check in `should_do_markup`, so it beats an inherited
        `FORCE_COLOR` — but that is a claim about pytest's internals, and this is where it is
        verified instead of assumed.
        """
        import sys

        from _pytest._io.terminalwriter import should_do_markup

        assert should_do_markup(sys.stdout) is False
