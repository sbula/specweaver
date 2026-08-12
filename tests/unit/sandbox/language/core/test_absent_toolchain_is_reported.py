# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No QA runner may report an absent toolchain as a clean run (`TECH-032`).

`TECH-031` fixed this for Python. The same hole was open in every other language runner: the
subprocess exits non-zero with empty stdout, the parser finds nothing to report, and "nothing to
report" is indistinguishable from "nothing wrong". **The gate certifies a run that never
happened.**

Demonstrated with a real `SubprocessExecutor` on 2026-08-12, not inferred: `JavaRunner.run_tests`
returns byte-identical `passed=0 failed=0 errors=0` whether or not `javac` is on `PATH`. On this
machine the toolchains live under `~/.sdkman` and `~/.cargo` and are **not** on a fresh shell's
`PATH`, so that mistake is a daily one rather than a hypothetical.

Written as a census over every registered runner rather than one test per hole, so a **new**
language cannot arrive with the defect intact — which is how it reached four runners.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult

if TYPE_CHECKING:
    from collections.abc import Iterator

#: Every language runner, as (module suffix, class name).
RUNNERS = [
    ("python", "PythonQARunner"),
    ("java", "JavaRunner"),
    ("kotlin", "KotlinRunner"),
    ("rust", "RustRunner"),
    ("typescript", "TypeScriptRunner"),
]

#: The QA surface each runner may implement.
METHODS = (
    "run_tests",
    "run_linter",
    "run_complexity",
    "run_architecture_check",
    "run_compiler",
)

#: What a shell reports for a command that is not installed: nothing on stdout, non-zero exit.
ABSENT = SubprocessResult(
    exit_code=127,
    stdout="",
    stderr="/bin/sh: 1: javac: not found",
    timed_out=False,
    duration_seconds=0.1,
)


def _runner_class(module_suffix: str, class_name: str) -> Any:
    module = importlib.import_module(f"specweaver.sandbox.language.core.{module_suffix}.runner")
    return getattr(module, class_name)


def _reported_a_problem(result: Any) -> bool:
    """Whether a QA result says something is wrong, across the five result shapes."""
    return any(getattr(result, field, 0) for field in ("errors", "error_count", "violation_count"))


def _executor_backed_paths() -> Iterator[tuple[str, str]]:
    """Every (runner, method) that actually shells out.

    Methods that never call the executor are declared `STUB`s returning zeros — unimplemented, not
    a toolchain failure, and explicitly out of `TECH-032`'s scope. They are skipped rather than
    silently counted as passing, so this census cannot flatter itself.

    Discovery runs in a **real** temporary directory. An earlier version probed with a nonexistent
    path; the TypeScript methods raised while writing their config there, were skipped as
    "unreachable", and silently dropped out of the parametrisation — the same
    a-check-that-does-not-run-looks-like-one-that-passes failure this whole ticket is about.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as probe_dir:
        for suffix, class_name in RUNNERS:
            cls = _runner_class(suffix, class_name)
            for method in METHODS:
                if not hasattr(cls, method):
                    continue
                executor = MagicMock(spec=SubprocessExecutor)
                executor.execute.return_value = ABSENT
                try:
                    getattr(cls(cwd=Path(probe_dir), executor=executor), method)(target=".")
                except Exception:
                    continue
                if executor.execute.called:
                    yield suffix, method


ABSENT_TOOLCHAIN_PATHS = sorted(_executor_backed_paths())


@pytest.mark.parametrize(("language", "method"), ABSENT_TOOLCHAIN_PATHS)
def test_an_absent_toolchain_is_reported_not_passed(
    language: str, method: str, tmp_path: Path
) -> None:
    """Exit 127 with no output must produce a reported problem, never a clean result."""
    suffix, class_name = next(r for r in RUNNERS if r[0] == language)
    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.return_value = ABSENT

    runner = _runner_class(suffix, class_name)(cwd=tmp_path, executor=executor)
    result = getattr(runner, method)(target=".")

    assert _reported_a_problem(result), (
        f"{language}.{method} reported a clean run for a toolchain that is not installed — "
        f"got {result!r}"
    )


def test_the_census_actually_found_the_runners() -> None:
    """Guards the parametrisation against silently collapsing to nothing.

    If a refactor moved or renamed the runners, `_executor_backed_paths` would yield nothing, the
    parametrised test would vanish, and the suite would still be green — the exact failure mode
    this ticket exists to remove.
    """
    languages = {language for language, _ in ABSENT_TOOLCHAIN_PATHS}

    assert len(ABSENT_TOOLCHAIN_PATHS) >= 17, (
        f"expected at least 17 executor-backed QA paths, found {len(ABSENT_TOOLCHAIN_PATHS)}"
    )
    assert {"python", "java", "kotlin", "rust", "typescript"} <= languages, (
        f"a whole runner dropped out of the census: {sorted(languages)}"
    )
