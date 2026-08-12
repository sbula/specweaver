# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The dependency manifest declares each name once, and the default command produces a usable env.

`uv` installs dependency-groups by default and extras only on request. A name that exists as both
therefore means two different sets depending on which flag the caller passed — and the caller has no
way to know that from the name alone.

This is not hypothetical. `dev` was declared in both, split so that `pytest-xdist` was in the group
and `pytest` in the extra, so a plain `uv sync` installed the parallel-test plugin without the test
runner. The suite then ran and reported **5347 errors**, because `pytest` resolves transitively
through `xdist` and the absent `pytest-asyncio` is a hard error under `pytest 9`. Three documents
said `--all-extras`, which is how a wrong default survived being written down.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

#: Every tool the test suite, lint gate and boundary check invoke. `quality.py` shells out to
#: ruff/mypy/tach, `tests.py` needs pytest and xdist, and the sandbox's own QA runner calls
#: `python -m pytest` / `-m ruff` / `-m tach` from whatever venv a bare sync produced.
REQUIRED_DEV_TOOLS = ("pytest", "pytest-asyncio", "pytest-xdist", "ruff", "mypy", "tach")


def _manifest() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _names(entries: list[str]) -> set[str]:
    """Requirement strings reduced to bare distribution names."""
    out = set()
    for entry in entries:
        name = entry.split(";")[0].strip()
        for sep in (">=", "<=", "==", "!=", "~=", ">", "<", "["):
            name = name.split(sep)[0]
        out.add(name.strip().lower())
    return out


def test_no_name_is_both_a_dependency_group_and_an_extra() -> None:
    """One name, one meaning. Two would mean the flag decides which set you get.

    The cheap parse that stops the original defect regrowing: it cannot detect every way a manifest
    can be wrong, but it does detect the exact collision that produced 5347 errors.
    """
    manifest = _manifest()
    groups = set(manifest.get("dependency-groups", {}))
    extras = set(manifest.get("project", {}).get("optional-dependencies", {}))

    collisions = sorted(groups & extras)

    assert collisions == [], (
        f"declared as both a dependency-group and an extra: {collisions}. "
        "`uv sync` installs groups by default and extras on request, so the same name means two "
        "different sets depending on the flag."
    )


def test_the_default_sync_installs_every_tool_the_gates_need() -> None:
    """A bare `uv sync` must produce an environment the project's own gates can run in.

    Asserted against the manifest rather than the live venv on purpose: this must fail on a machine
    where someone already ran `--all-extras`, which is precisely the machine where the defect is
    invisible.

    The sandbox raises the stakes past developer convenience — `B-EXEC-01`'s prepare phase runs a
    bare `uv sync` and its QA runner then calls `python -m pytest` from that venv, so a tool missing
    here is a tool missing from sandboxed QA.
    """
    manifest = _manifest()
    default_groups = manifest.get("dependency-groups", {})
    installed = set()
    for entries in default_groups.values():
        installed |= _names([e for e in entries if isinstance(e, str)])

    missing = sorted(t for t in REQUIRED_DEV_TOOLS if t not in installed)

    assert missing == [], (
        f"not installed by a default `uv sync`: {missing}. Dependency-groups install by default; "
        "extras do not, so a gate tool placed in an extra is absent until someone remembers a flag."
    )


def test_the_optional_extras_are_genuinely_optional_features() -> None:
    """Extras are for user-facing choices, not for things the project needs to test itself.

    Pins the distinction the collision blurred: `openai` or `serve` are real choices an installer
    makes, while `pytest` is not optional to anyone who runs the suite.
    """
    extras = set(_manifest().get("project", {}).get("optional-dependencies", {}))

    assert "dev" not in extras, (
        "`dev` is not an optional feature — it is what the project needs to test itself, and "
        "belongs in [dependency-groups] so a default sync installs it."
    )
    assert extras, "expected the genuine feature extras (openai, serve, ...) to remain"
