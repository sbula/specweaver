# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the sandbox will do with a project's dependencies, decided once.

The container executor acts on this and `sw sandbox preflight` prints it. Deciding it in one place
is the point: a preflight that re-derived the decision would agree with the sandbox only until one
of them changed, and a report describing something other than what runs is worse than no report.

Resides in L0 commons for the same reason as the QA result models beside it — the delivery layer
must be able to read this without importing the sandbox, and reading a manifest is knowledge about
packaging rather than a way to execute anything.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from specweaver.commons.tooling_sources import ToolingSource, declared_pytest

if TYPE_CHECKING:
    from pathlib import Path


#: The QA runner invokes `python -m pytest` and nothing else, so this is the entire predicate: a
#: group is worth syncing exactly when it puts pytest in the environment.
#:
#: `tox` and `nox` are deliberately absent even though both are test runners. They build their own
#: environments and would leave `python -m pytest` failing exactly as before, while installing the
#: rest of that group — and the prepare phase executes arbitrary sdist build code, so widening what
#: an untrusted project builds for no gain is the wrong trade. `coverage` is absent for the simpler
#: reason that it measures a run and cannot start one.
_TEST_RUNNERS: tuple[str, ...] = ("pytest",)

#: `uv sync` installs this group unasked. Requesting it again would be noise.
_DEFAULT_GROUP = "dev"

#: Installed only when the project names no runner anywhere. Bare: which plugins a suite needs
#: is exactly what the project failed to say, so guessing at them would add arbitrary packages
#: to an already arbitrary choice.
_LAST_RESORT_RUNNER = "pytest"


def _declares_a_runner(deps: list[object]) -> bool:
    """Whether a dependency-group's entries include something that can run a test suite."""
    for dep in deps:
        if not isinstance(dep, str):
            # A PEP 735 `{include-group = "..."}` table. The included group is judged on its own
            # entries, so following the reference here would only find it twice.
            continue
        name = re.split(r"[<>=!~;\[\s]", dep.strip(), maxsplit=1)[0].lower().replace("_", "-")
        if any(name == runner or name.startswith(f"{runner}-") for runner in _TEST_RUNNERS):
            return True
    return False


def _manifest_declares_a_runner(manifest_text: str) -> bool:
    """Whether `uv` can install pytest from this manifest alone, by group or at runtime.

    The gate on reading any other file. A project that declares pytest has pinned it, and layering a
    `tox.ini` block over that resolution would turn a reproducible run into a mixed one.
    """
    try:
        manifest = tomllib.loads(manifest_text)
    except (tomllib.TOMLDecodeError, ValueError):
        return False
    runtime = (manifest.get("project") or {}).get("dependencies")
    return bool(_groups_holding_a_runner(manifest_text)) or (
        isinstance(runtime, list) and _declares_a_runner(runtime)
    )


def _groups_holding_a_runner(manifest_text: str) -> list[str]:
    """Every PEP 735 group that declares pytest, `dev` included.

    `dev` is returned rather than filtered here because the two prepare paths disagree about it:
    `uv sync` installs it unasked, while `uv pip install` installs nothing it is not given. Dropping
    it at the source would silently strip the most common runner location from the second path.

    Detection is by content because the names are a long tail: `test`, `tests`, `testing`, `ci`,
    `test-core` and `dev-base` all carry pytest across the measured corpus, while
    `tests-postgresql` and `tests-mysql` carry database drivers and none. A name list would miss
    the first set and install the second.

    It is also the only safe rule. `uv sync --group <undeclared>` exits 2 rather than warning, so a
    speculative name would break the prepare phase for every project that does not use it; only
    groups this manifest actually declares are ever returned.

    A manifest that cannot be parsed yields no groups. Group detection improves the sync; it is
    never a new way for it to fail.
    """
    try:
        manifest = tomllib.loads(manifest_text)
    except (tomllib.TOMLDecodeError, ValueError):
        return []
    groups = manifest.get("dependency-groups")
    if not isinstance(groups, dict):
        return []
    return sorted(
        name for name, deps in groups.items() if isinstance(deps, list) and _declares_a_runner(deps)
    )


@dataclass(frozen=True)
class PreparePlan:
    """Everything the prepare phase decides before it runs a container."""

    #: `"locked"` — `uv sync --frozen`, reproducing the project's pins. `"resolved"` — `uv venv`
    #: plus `uv pip install`, resolving fresh because no `uv.lock` was committed.
    route: str
    #: Where the test runner comes from: a manifest group, a file, `"sandbox"`, or `""` when the
    #: project has no manifest for `uv` to read at all.
    runner_source: str
    groups: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    #: The declaration the runner was found in, when it came from outside the manifest. Carried so
    #: the executor installs exactly what the report described, rather than looking it up again.
    source: ToolingSource | None = None


def plan_for(source_root: Path) -> PreparePlan:
    """What the prepare phase will do with the project at `source_root`."""
    manifest = source_root / "pyproject.toml"
    manifest_text = (
        manifest.read_text(encoding="utf-8", errors="replace") if manifest.is_file() else ""
    )
    locked = (source_root / "uv.lock").is_file()
    route = "locked" if locked else "resolved"

    if not manifest_text and not locked:
        return PreparePlan(
            route="none",
            runner_source="",
            warnings=(
                "No pyproject.toml and no uv.lock, so no environment can be built at all. The QA "
                "run will use the container image's own interpreter, which has no test runner.",
            ),
        )

    warnings: list[str] = []
    if not locked:
        warnings.append(
            "No uv.lock, so dependencies are resolved fresh from pyproject.toml. The environment "
            "will NOT reproduce the project's pinned set. Commit a lockfile to make runs match CI."
        )

    groups = tuple(_groups_holding_a_runner(manifest_text))
    if _manifest_declares_a_runner(manifest_text):
        return PreparePlan(route, "pyproject.toml", groups, warnings=tuple(warnings))

    fallback: ToolingSource | None = declared_pytest(source_root)
    if fallback is not None:
        if fallback.skipped:
            warnings.append(
                f"{len(fallback.skipped)} line(s) of {fallback.path} need tox's own substitution "
                f"engine and will not be installed — plugins declared there will be missing."
            )
        return PreparePlan(
            route, fallback.path, groups, fallback.skipped, tuple(warnings), source=fallback
        )

    warnings.append(
        "No test runner is declared in pyproject.toml, tox.ini or any requirements file, so the "
        "sandbox will install pytest itself. Its version is not the project's choice and any "
        "plugins the suite needs will be absent — results will say so."
    )
    return PreparePlan(route, "sandbox", groups, warnings=tuple(warnings))
