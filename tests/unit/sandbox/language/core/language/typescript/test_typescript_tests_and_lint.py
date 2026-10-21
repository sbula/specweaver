# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript tests run through the project's `npm test`, lint through ESLint — no more stubs.

Proves: D-INTL-08 FR-5
Proves: D-INTL-08 FR-6

The executor is doubled; the commands and the reading of what comes back are the contract here. The
real `npm` run is in the `toolchain` tier (SF-05): it needs packages from the network.

| Bucket | Case |
|---|---|
| Happy | Jest's and Vitest's summary lines are read into counts; ESLint's JSON into errors |
| Boundary | one test file is passed after `--`; a folder target passes nothing; colour codes are stripped; an unknown test tool counts by its exit code |
| Degradation | `npm` or ESLint that never ran is a named failure, never "0 tests" or "0 errors" |
| Hostile | a `package.json` with no `test` script fails, naming it |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

if TYPE_CHECKING:
    from pathlib import Path


def _runner(
    tmp_path: Path,
    stdout: str = "",
    exit_code: int = 0,
    stderr: str = "",
    scripts: dict | None = None,
):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "jest"} if scripts is None else scripts}), encoding="utf-8"
    )
    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.return_value = SubprocessResult(
        exit_code=exit_code, stdout=stdout, stderr=stderr, timed_out=False, duration_seconds=0.2
    )
    return TypeScriptRunner(cwd=tmp_path, executor=executor), executor


def _command(executor: MagicMock) -> list[str]:
    return list(executor.execute.call_args[0][0])


_JEST = "PASS tests/a.test.ts\nTests:       1 failed, 2 passed, 3 total\nTime: 1 s\n"
_VITEST = (
    " ✓ tests/a.test.ts (2)\n Test Files  1 passed (1)\n      Tests  1 failed | 2 passed (3)\n"
)


def test_one_file_is_passed_after_the_separator(tmp_path: Path) -> None:
    runner, executor = _runner(tmp_path, _JEST, exit_code=1)

    runner.run_tests(target="tests/greet.test.ts")

    assert _command(executor)[-3:] == ["test", "--", "tests/greet.test.ts"]


def test_a_folder_target_passes_nothing(tmp_path: Path) -> None:
    runner, executor = _runner(tmp_path, _JEST, exit_code=1)

    runner.run_tests(target=".")

    assert "--" not in _command(executor)


@pytest.mark.parametrize(
    "stdout", [_JEST, _VITEST, "\x1b[1m" + _VITEST.replace("Tests", "\x1b[2mTests\x1b[22m")]
)
def test_the_summary_line_is_read(tmp_path: Path, stdout: str) -> None:
    runner, _ = _runner(tmp_path, stdout, exit_code=1)

    result = runner.run_tests(target="tests/a.test.ts")

    assert (result.passed, result.failed, result.total) == (2, 1, 3), result


def test_an_all_green_jest_run(tmp_path: Path) -> None:
    runner, _ = _runner(tmp_path, "Tests:       3 passed, 3 total\n")

    result = runner.run_tests(target=".")

    assert (result.passed, result.failed, result.total) == (3, 0, 3)


@pytest.mark.parametrize(("exit_code", "passed", "failed"), [(0, 1, 0), (1, 0, 1)])
def test_an_unknown_tool_counts_by_its_exit_code(
    tmp_path: Path, exit_code: int, passed: int, failed: int
) -> None:
    runner, _ = _runner(tmp_path, "ok from mocha-ish\n", exit_code=exit_code)

    result = runner.run_tests(target=".")

    assert (result.passed, result.failed, result.total) == (passed, failed, 1), result


def test_no_test_script_fails_naming_it(tmp_path: Path) -> None:
    runner, executor = _runner(tmp_path, scripts={"build": "tsc"})

    result = runner.run_tests(target=".")

    assert result.errors == 1
    assert "test" in result.failures[0].message
    executor.execute.assert_not_called()


def test_npm_that_never_ran_is_a_named_failure(tmp_path: Path) -> None:
    runner, _ = _runner(tmp_path, "", exit_code=127, stderr="npm: not found")

    result = runner.run_tests(target=".")

    assert result.errors == 1
    assert "npm" in result.failures[0].message


_ESLINT = json.dumps(
    [
        {
            "filePath": "/p/src/a.ts",
            "errorCount": 2,
            "fixableErrorCount": 1,
            "messages": [
                {"ruleId": "no-unused-vars", "severity": 2, "message": "x is unused", "line": 3},
                {"ruleId": "semi", "severity": 2, "message": "Missing semicolon", "line": 4},
            ],
        },
        {"filePath": "/p/src/b.ts", "errorCount": 0, "fixableErrorCount": 0, "messages": []},
    ]
)


def test_eslint_json_is_read(tmp_path: Path) -> None:
    runner, executor = _runner(tmp_path, _ESLINT, exit_code=1)

    result = runner.run_linter(target="src/a.ts")

    assert _command(executor)[-4:] == ["eslint", "src/a.ts", "--format", "json"]
    assert (result.error_count, result.fixable_count) == (2, 1)
    assert [error.code for error in result.errors] == ["no-unused-vars", "semi"]


def test_fix_asks_eslint_to_fix(tmp_path: Path) -> None:
    runner, executor = _runner(tmp_path, "[]")

    runner.run_linter(target="src/a.ts", fix=True)

    assert "--fix" in _command(executor)


def test_eslint_that_did_not_run_is_never_clean(tmp_path: Path) -> None:
    runner, _ = _runner(tmp_path, "Oops! Something went wrong!", exit_code=2)

    result = runner.run_linter(target="src/a.ts")

    assert result.error_count >= 1
    assert result.errors[0].code == "ToolchainUnavailable"
