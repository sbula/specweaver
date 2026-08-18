# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a project declares its test runner when `pyproject.toml` does not.

Two thirds of real repositories never name pytest in their manifest: measured across the 150
most-downloaded PyPI packages, 81 of 121. Most of them do declare it — in `tox.ini`, or in one of a
family of `requirements` spellings — just not anywhere `uv sync` will ever look.

**This reads those files; it does not emulate the tools that own them.** All 30 corpus `tox.ini`
files were parsed while writing it: 891 dependency lines carry `{...}` substitution — tox factors
like `py3{10-14}: -r reqs.pip`, `{[testenv]deps}` back-references, `{toxinidir}` paths — against 236
plain requirement lines. Resolving those is implementing tox. What cannot be read is reported as
skipped rather than dropped, so an incomplete environment does not look like a complete one.
"""

from __future__ import annotations

import configparser
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

#: Checked in order, and the first that names pytest wins. Requirements files come first because
#: `uv pip install -r` reads the format natively — no parsing, and its own `-r` includes resolve
#: themselves. Installing a tox block *as well* would risk two conflicting pins of one package.
_REQUIREMENT_FILES: tuple[str, ...] = (
    "requirements-dev.txt",
    "requirements_dev.txt",
    "dev-requirements.txt",
    "test-requirements.txt",
    "requirements-test.txt",
    "requirements/dev.txt",
    "requirements/test.txt",
    "requirements/tests.txt",
)

_PYTEST = re.compile(r"^pytest(\b|[<>=!~\[])", re.I)
#: A tox factor conditional — `py39: pytest`, `lint: -r dev-requirements.txt`. Selecting the right
#: one means knowing which environment tox would have run.
_FACTOR = re.compile(r"^[A-Za-z0-9_.,{}-]+:\s")


@dataclass(frozen=True)
class ToolingSource:
    """What to install, and what could not be read while working it out."""

    path: str
    requirement_files: tuple[str, ...] = ()
    packages: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()


def declared_pytest(root: Path) -> ToolingSource | None:
    """The first readable declaration of pytest outside `pyproject.toml`, or None."""
    for name in _REQUIREMENT_FILES:
        candidate = root / name
        if candidate.is_file() and _names_pytest(_read(candidate)):
            return ToolingSource(path=name, requirement_files=(name,))
    return _from_tox(root / "tox.ini")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _names_pytest(text: str) -> bool:
    return any(_PYTEST.match(line.strip()) for line in text.splitlines())


def _classify(line: str) -> tuple[str, str] | None:
    """One tox dependency line as `(kind, value)`, or None when there is nothing to install.

    `skip` is a first-class outcome, not a failure: those lines are reported to the caller so a
    partial environment cannot pass for a complete one.
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "{" in line or _FACTOR.match(line) or line.startswith(("-c", "-e", ".")):
        return ("skip", line)
    if line.startswith("-r"):
        # `-rfile.txt` with no space is valid tox and appears in the corpus.
        return ("include", line[2:].strip())
    return ("package", line)


def _testenv_deps(parser: configparser.ConfigParser) -> list[str]:
    """Every dependency line of every `testenv` section, in file order."""
    lines: list[str] = []
    for section in parser.sections():
        if section == "testenv" or section.startswith("testenv:"):
            lines.extend(parser.get(section, "deps", fallback="").splitlines())
    return lines


def _from_tox(tox: Path) -> ToolingSource | None:
    """The plain lines of every `testenv` dependency block, if one of them is pytest."""
    if not tox.is_file():
        return None
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(_read(tox))
    except configparser.Error:
        # Reading a foreign format is best-effort. A malformed tox.ini is the project's problem to
        # fix, never a reason for the prepare phase to stop building an environment.
        return None

    buckets: dict[str, list[str]] = {"package": [], "include": [], "skip": []}
    for raw in _testenv_deps(parser):
        classified = _classify(raw)
        if classified is not None:
            buckets[classified[0]].append(classified[1])

    if not any(_PYTEST.match(package) for package in buckets["package"]):
        # A block of lint tooling is not a test runner, and installing it does not make
        # `python -m pytest` work.
        return None
    return ToolingSource(
        path="tox.ini",
        requirement_files=tuple(dict.fromkeys(buckets["include"])),
        packages=tuple(dict.fromkeys(buckets["package"])),
        skipped=tuple(buckets["skip"]),
    )
