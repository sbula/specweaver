# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Live tests cost real money, so nothing may run them by accident.

A live test calls a paid API over the network. That makes it the one tier where an accidental
run is not merely slow: it bills, it can leak a key into a log, and it fails for reasons that
have nothing to do with the change under test.

Three things keep it opt-in, and each is one edit away from being lost:

1. `addopts` deselects the marker, so a bare `pytest` skips them.
2. No gate script re-enables it, so no commit boundary can start paying.
3. The tests carry the marker, so the deselection actually catches them.

Delete any one and the protection is gone silently — every run still passes, and the bill is the
only signal. These assertions are the alarm.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
SCRIPTS = REPO_ROOT / "scripts"
LIVE_TESTS = REPO_ROOT / "tests" / "manual" / "test_llm_live.py"

#: `-m 'not live'` written as one shell string.
_MARKER_FLAG = re.compile(r"""-m\s*(?:'([^']*)'|"([^"]*)"|(\S+))""")

#: `"-m", "live"` — the flag and its expression as two list items, which is how every script here
#: actually builds a command. Missing this form was the whole point of testing the guard.
_MARKER_PAIR = re.compile(r"""["']-m["']\s*,\s*["']([^"']*)["']""")


def _marker_expressions(source: str) -> list[str]:
    """Every marker expression a `-m` in this source carries, in either form."""
    found = [
        next(group for group in match.groups() if group is not None)
        for match in _MARKER_FLAG.finditer(source)
    ]
    found.extend(match.group(1) for match in _MARKER_PAIR.finditer(source))
    return found


def _enables_live(source: str) -> bool:
    """Does this source select live tests for *execution*?

    `-m 'not live'` is the opposite and must not count, or the guard flags the very line that
    protects us. Neither does dropping the filter for `--collect-only`: collecting a live test
    names it, it does not call the API.
    """
    return any(
        re.search(r"\blive\b", expression) and not re.search(r"\bnot\s+live\b", expression)
        for expression in _marker_expressions(source)
    )


def _addopts() -> str:
    with PYPROJECT.open("rb") as handle:
        config = tomllib.load(handle)
    return str(config["tool"]["pytest"]["ini_options"]["addopts"])


def test_a_bare_pytest_run_deselects_live_tests() -> None:
    """The first line of defence: `pytest` with no arguments must not call a paid API."""
    assert re.search(r"-m\s*'not live'|-m\s*\"not live\"", _addopts()), (
        "pyproject.toml addopts no longer deselects the `live` marker — "
        "every ordinary test run will now call the real LLM APIs and bill for it"
    )


def test_no_gate_script_re_enables_the_live_marker() -> None:
    """The second: a commit boundary must stay free and offline."""
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in SCRIPTS.rglob("*.py")
        if _enables_live(path.read_text(encoding="utf-8"))
    ]

    assert offenders == [], (
        f"gate script(s) select the `live` marker: {offenders}. "
        "Live tests are opt-in and run by hand, never at a gate"
    )


def test_the_live_tests_actually_carry_the_marker() -> None:
    """The third. A deselection only protects tests that are marked.

    Without this, an unmarked live test would run in every ordinary suite and the two assertions
    above would still be green.
    """
    source = LIVE_TESTS.read_text(encoding="utf-8")
    tests = re.findall(r"^async def (test_\w+)|^def (test_\w+)", source, re.MULTILINE)

    assert tests, f"{LIVE_TESTS.name} has no tests — this guard is watching nothing"
    assert source.count("@pytest.mark.live") == len(tests), (
        f"{LIVE_TESTS.name} has {len(tests)} test(s) but "
        f"{source.count('@pytest.mark.live')} `live` marker(s) — an unmarked one runs everywhere"
    )
