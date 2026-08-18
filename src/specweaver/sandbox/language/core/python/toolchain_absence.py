# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Turning "the interpreter said nothing" into something the reader can act on.

`did_not_run` in the shared toolchain module tells a silent run apart from a real verdict, which is
what stops a missing toolchain being certified as a pass. It reports the last line of stderr, and
for the single most common failure that line is:

    /cache/venv/bin/python: No module named pytest

`/cache/venv` is a path inside our own container. It appears nowhere in the reader's project, so the
message names an artefact they cannot inspect, while saying nothing about why pytest is absent or
what would make it present.

This is not an edge case. Of the 121 resolvable repositories among the 150 most-downloaded PyPI
packages, 101 reach the sandbox without pytest installed and 81 never declare it in
`pyproject.toml` at all — so this is the first thing most new targets say.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.sandbox.language.core.toolchain import did_not_run

if TYPE_CHECKING:
    from specweaver.sandbox.execution.models import SubprocessResult

#: `python -m X` with X absent. The interpreter prints its own path first, which is why the
#: forwarded line leaked a container path: the useful half is everything after the colon.
_NO_MODULE = re.compile(r"No module named ['\"]?(?P<module>[A-Za-z0-9_.-]+)['\"]?")


def absent_module(result: SubprocessResult) -> str | None:
    """Why the run produced nothing, when the reason is that the tool is not installed.

    Returns None for anything else, including a run that produced output: pytest can name a missing
    module in a collection error while running perfectly well, and rewriting that as a setup failure
    would hide a real test failure behind a manifest complaint.
    """
    if result.stdout.strip():
        return None
    match = _NO_MODULE.search(result.stderr or "")
    if match is None:
        return None

    module = match.group("module")
    return (
        f"{module} is not installed in the environment this run used, so nothing was executed. "
        f"This is a setup failure, not a test failure — the tests were never reached. "
        f"The environment is whatever `uv sync` builds from the project manifest: a dependency "
        f"group it installs (`dev`, or any group that declares {module}) or the runtime "
        f"dependencies, resolved from a committed `uv.lock`. Declare {module} in one of those and "
        f"commit the lockfile. On a host run, install it into the active virtualenv instead."
    )


def why_it_did_not_run(result: SubprocessResult, tool: str) -> str | None:
    """`did_not_run`, with the missing-module case explained rather than forwarded.

    Every tool this runner drives goes through `python -m` — pytest, ruff for both linting and
    complexity — so all of them fail this way when the prepared environment is incomplete, and all
    of them produced the same unreadable line. Anything the pattern does not recognise falls back to
    the shared behaviour unchanged.
    """
    reason = did_not_run(result, tool)
    if reason is None:
        return None
    return absent_module(result) or reason


def supplied_note(executor: object) -> str:
    """What to tell the reader when the runner was not the project's own.

    A project that declares no test runner anywhere still gets one, so its suite can run at all.
    That makes a green result an attestation about a version nobody chose, with none of the plugins
    the suite may need — the one thing a caller must not have to infer.
    """
    supplied = getattr(executor, "supplied_toolchain", ())
    if not supplied:
        return ""
    names = ", ".join(supplied)
    return (
        f"This run used {names} supplied by the sandbox: the project does not declare a test "
        f"runner in pyproject.toml, tox.ini or any requirements file. The version is not declared "
        f"by the project, and any plugins its tests rely on are absent, so a passing result "
        f"describes this environment rather than the project's own."
    )
