# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw` still renders in colour, and still reads without it.

Proves: TECH-050 FR-3

`tests/conftest.py` pins the whole suite colour-free, which fixes 28 failures and costs one thing:
nothing would then exercise the coloured path at all. This buys that back.

It has to be a **subprocess**. `specweaver.interfaces.cli._core` builds its `Console` at module
import, so the renderer has already decided about colour before any fixture runs — `monkeypatch`
cannot change its mind, and an in-process test would prove only that the decision was cached. The
claim is about the shipped command, so the shipped command is what runs.

Without this, `sw` could stop emitting colour entirely — a broken `Console`, a swallowed markup tag
— and nothing would notice, because every other test now reads output with the colour removed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.rendering import shows

#: The repo root, found by walking up to `pyproject.toml` rather than counting directories. A
#: hardcoded `parents[N]` broke silently when this file moved into its capability folder under
#: `C-EXEC-03` FR-8; the next restructure should not get a second chance.
REPO_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _version(**env_over: str) -> str:
    env = {**os.environ, "PATH": os.environ.get("PATH", ""), **env_over}
    for key, value in list(env.items()):
        if value is None:  # pragma: no cover - defensive
            env.pop(key)
    done = subprocess.run(
        [sys.executable, "-m", "specweaver.interfaces.cli.main", "--version"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout + done.stderr


@pytest.mark.e2e
class TestMainRendersColour:
    """The path the rest of the suite deliberately no longer touches."""

    def test_it_emits_escapes_when_the_environment_asks_for_colour(self) -> None:
        out = _version(FORCE_COLOR="3", NO_COLOR="", PY_COLORS="")
        assert _ANSI.search(out), f"colour was requested; no escapes in {out!r}"

    def test_it_emits_none_when_the_environment_forbids_colour(self) -> None:
        """The mode the suite runs in. If this ever fails, 28 tests come back."""
        out = _version(NO_COLOR="1", FORCE_COLOR="")
        assert not _ANSI.search(out), f"colour was forbidden; escapes in {out!r}"

    def test_the_content_is_the_same_either_way(self) -> None:
        """Colour must decorate the output, never replace or corrupt it.

        This is the assertion the 28 failures were making badly: the version *is* there, split by
        an escape Rich puts mid-token. `shows` reads it in both modes.
        """
        coloured = _version(FORCE_COLOR="3", NO_COLOR="", PY_COLORS="")
        plain = _version(NO_COLOR="1", FORCE_COLOR="")
        assert shows(coloured, "SpecWeaver")
        assert shows(plain, "SpecWeaver")
        assert _ANSI.sub("", coloured).strip() == plain.strip()
