# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A lint or complexity check that did not run never reads as clean, in any runner.

Proves: TECH-087 FR-1, FR-2, FR-3

Each case is one place a runner returned zero findings for a tool that timed out, found no container
engine, wrote no report, wrote one that cannot be read, or left an earlier run's report to be read
as today's. Every one must come back as the shared not-run result (`toolchain.failed_lint` /
`failed_complexity`): count 1 at `<toolchain>`, with a reason naming the tool. The controls beside
them keep a real empty verdict clean.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.sandbox.execution.container_executor import ContainerEngineUnavailableError
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.java.runner import JavaRunner
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner
from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.language.core.rust.runner import RustRunner
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.sandbox.qa_runner.core.interface import ComplexityRunResult, LintRunResult


def _result(
    *, exit_code: int = 0, stdout: str = "", stderr: str = "", timed_out: bool = False
) -> SubprocessResult:
    return SubprocessResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_seconds=0.1,
    )


def _executor(**kwargs: object) -> MagicMock:
    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.return_value = _result(**kwargs)  # type: ignore[arg-type]
    return executor


def _assert_lint_did_not_run(result: LintRunResult, *says: str) -> None:
    assert result.error_count == 1
    [error] = result.errors
    assert (error.file, error.code) == ("<toolchain>", "ToolchainUnavailable")
    for needle in says:
        assert needle in error.message


def _assert_complexity_did_not_run(result: ComplexityRunResult, *says: str) -> None:
    assert result.violation_count == 1
    [violation] = result.violations
    assert (violation.file, violation.function) == ("<toolchain>", "<toolchain>")
    for needle in says:
        assert needle in violation.message


_CLEAN_SARIF = json.dumps({"version": "2.1.0", "runs": [{"results": []}]})
_ONE_FINDING_SARIF = json.dumps(
    {
        "runs": [
            {
                "results": [
                    {
                        "ruleId": "UnusedImport",
                        "message": {"text": "unused import"},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "src/A.java"},
                                    "region": {"startLine": 3},
                                }
                            }
                        ],
                    }
                ]
            }
        ]
    }
)


# ---------------------------------------------------------------------------
# Python: S1-S6
# ---------------------------------------------------------------------------


class TestPython:
    def test_lint_without_a_container_engine_did_not_run(self, tmp_path: Path) -> None:
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.side_effect = ContainerEngineUnavailableError("no engine found")

        result = PythonQARunner(cwd=tmp_path, executor=executor).run_linter(target="src/")

        _assert_lint_did_not_run(result, "no engine found")

    def test_lint_that_timed_out_did_not_run_even_with_output(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path, executor=_executor(stdout="[]", timed_out=True))

        result = runner.run_linter(target="src/")

        _assert_lint_did_not_run(result, "ruff timed out after 120 s")

    @pytest.mark.parametrize("stdout", ["not json", "{}", '{"errors": []}'])
    def test_lint_whose_report_is_not_ruffs_did_not_run(self, tmp_path: Path, stdout: str) -> None:
        runner = PythonQARunner(cwd=tmp_path, executor=_executor(exit_code=1, stdout=stdout))

        result = runner.run_linter(target="src/")

        _assert_lint_did_not_run(result, "ruff")

    def test_lint_with_ruffs_empty_list_is_clean(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path, executor=_executor(stdout="[]"))

        result = runner.run_linter(target="src/")

        assert (result.error_count, result.errors) == (0, [])

    def test_ruff_that_never_started_names_ruff(self, tmp_path: Path) -> None:
        runner = PythonQARunner(
            cwd=tmp_path, executor=_executor(exit_code=1, stderr="No module named ruff")
        )

        _assert_lint_did_not_run(runner.run_linter(target="src/"), "ruff is not installed")
        _assert_complexity_did_not_run(
            runner.run_complexity(target="src/"), "ruff is not installed"
        )

    def test_complexity_without_a_container_engine_did_not_run(self, tmp_path: Path) -> None:
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.side_effect = ContainerEngineUnavailableError("no engine found")

        result = PythonQARunner(cwd=tmp_path, executor=executor).run_complexity(target="src/")

        _assert_complexity_did_not_run(result, "no engine found")
        assert result.max_complexity == 10

    def test_complexity_that_timed_out_did_not_run(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path, executor=_executor(stdout="[]", timed_out=True))

        result = runner.run_complexity(target="src/", max_complexity=7)

        _assert_complexity_did_not_run(result, "ruff timed out after 120 s")
        assert result.max_complexity == 7

    def test_complexity_whose_report_is_not_ruffs_did_not_run(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path, executor=_executor(exit_code=1, stdout="garbage"))

        _assert_complexity_did_not_run(runner.run_complexity(target="src/"), "ruff")

    def test_complexity_with_ruffs_empty_list_is_clean(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path, executor=_executor(stdout="[]"))

        assert runner.run_complexity(target="src/").violation_count == 0

    def test_a_garbled_fix_pass_still_lets_the_final_check_decide(self, tmp_path: Path) -> None:
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.side_effect = [
            _result(),  # ruff format
            _result(exit_code=1, stdout="garbage"),  # ruff check --fix
            _result(stdout="[]"),  # the final check
        ]

        result = PythonQARunner(cwd=tmp_path, executor=executor).run_linter("src/", fix=True)

        assert (result.error_count, result.fixed_count) == (0, 0)


# ---------------------------------------------------------------------------
# Java and Kotlin: S8, S9, S10, S12
# ---------------------------------------------------------------------------

_JVM = [
    pytest.param(JavaRunner, "pom.xml", ("target", "pmd.sarif"), "pmd", id="java"),
    pytest.param(KotlinRunner, "pom.xml", ("target", "detekt.sarif"), "detekt", id="kotlin"),
]


def _writes_report(report: Path, text: str | None, **result: object) -> MagicMock:
    """An executor whose run writes `text` to the report (or nothing, for None)."""

    def run(*_args: object, **_kwargs: object) -> SubprocessResult:
        if text is not None:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(text, encoding="utf-8")
        return _result(**result)  # type: ignore[arg-type]

    executor = MagicMock(spec=SubprocessExecutor)
    executor.execute.side_effect = run
    return executor


@pytest.mark.parametrize(("runner_cls", "marker", "report_parts", "tool"), _JVM)
class TestJvm:
    @pytest.mark.parametrize("text", ["{", "[]", "null"])
    def test_a_report_that_cannot_be_read_did_not_run(
        self,
        tmp_path: Path,
        runner_cls: type,
        marker: str,
        report_parts: tuple,
        text: str,
        tool: str,
    ) -> None:
        (tmp_path / marker).touch()
        report = tmp_path.joinpath(*report_parts)
        executor = _writes_report(report, text, stdout="BUILD SUCCESS")
        runner = runner_cls(cwd=tmp_path, executor=executor)

        _assert_lint_did_not_run(runner.run_linter(target=""), report.name)
        _assert_complexity_did_not_run(runner.run_complexity(target=""), report.name)

    def test_a_report_that_is_a_directory_did_not_run(
        self, tmp_path: Path, runner_cls: type, marker: str, report_parts: tuple, tool: str
    ) -> None:
        (tmp_path / marker).touch()
        report = tmp_path.joinpath(*report_parts)
        executor = MagicMock(spec=SubprocessExecutor)

        def make_a_directory(*_args: object, **_kwargs: object) -> SubprocessResult:
            report.mkdir(parents=True, exist_ok=True)
            return _result(stdout="BUILD SUCCESS")

        executor.execute.side_effect = make_a_directory
        runner = runner_cls(cwd=tmp_path, executor=executor)

        _assert_lint_did_not_run(runner.run_linter(target=""), report.name)
        _assert_complexity_did_not_run(runner.run_complexity(target=""), report.name)

    def test_an_old_report_that_links_outside_removes_only_the_link(
        self, tmp_path: Path, runner_cls: type, marker: str, report_parts: tuple, tool: str
    ) -> None:
        project = tmp_path / "project"
        project.mkdir()
        (project / marker).touch()
        outside = tmp_path / "outside.sarif"
        outside.write_text(_CLEAN_SARIF, encoding="utf-8")
        report = project.joinpath(*report_parts)
        report.parent.mkdir(parents=True)
        report.symlink_to(outside)
        executor = _writes_report(report, None, stdout="BUILD SUCCESS")

        result = runner_cls(cwd=project, executor=executor).run_linter(target="")

        _assert_lint_did_not_run(result, report.name)
        assert outside.read_text(encoding="utf-8") == _CLEAN_SARIF

    def test_a_run_that_timed_out_did_not_run_even_with_a_report(
        self, tmp_path: Path, runner_cls: type, marker: str, report_parts: tuple, tool: str
    ) -> None:
        (tmp_path / marker).touch()
        report = tmp_path.joinpath(*report_parts)
        executor = _writes_report(report, _CLEAN_SARIF, stdout="partial", timed_out=True)
        runner = runner_cls(cwd=tmp_path, executor=executor)

        _assert_lint_did_not_run(runner.run_linter(target=""), tool, "timed out")
        _assert_complexity_did_not_run(runner.run_complexity(target=""), tool, "timed out")

    def test_an_earlier_runs_report_is_not_todays_verdict(
        self, tmp_path: Path, runner_cls: type, marker: str, report_parts: tuple, tool: str
    ) -> None:
        (tmp_path / marker).touch()
        report = tmp_path.joinpath(*report_parts)
        report.parent.mkdir(parents=True)
        report.write_text(_CLEAN_SARIF, encoding="utf-8")
        executor = _writes_report(report, None, exit_code=1, stdout="BUILD FAILURE")
        runner = runner_cls(cwd=tmp_path, executor=executor)

        _assert_lint_did_not_run(runner.run_linter(target=""), report.name)
        report.write_text(_CLEAN_SARIF, encoding="utf-8")
        _assert_complexity_did_not_run(runner.run_complexity(target=""), report.name)

    def test_an_old_report_that_cannot_be_removed_stops_the_run(
        self, tmp_path: Path, runner_cls: type, marker: str, report_parts: tuple, tool: str
    ) -> None:
        (tmp_path / marker).touch()
        report = tmp_path.joinpath(*report_parts)
        report.mkdir(parents=True)
        (report / "keep").touch()  # a non-empty directory where the report goes: unlink fails
        executor = _writes_report(report, None, stdout="BUILD SUCCESS")
        runner = runner_cls(cwd=tmp_path, executor=executor)

        _assert_lint_did_not_run(runner.run_linter(target=""), "cannot clear the old report")
        _assert_complexity_did_not_run(runner.run_complexity(target=""), "cannot clear")
        executor.execute.assert_not_called()

    def test_todays_clean_report_is_clean(
        self, tmp_path: Path, runner_cls: type, marker: str, report_parts: tuple, tool: str
    ) -> None:
        (tmp_path / marker).touch()
        report = tmp_path.joinpath(*report_parts)
        runner = runner_cls(
            cwd=tmp_path, executor=_writes_report(report, _CLEAN_SARIF, stdout="ok")
        )

        assert runner.run_linter(target="").error_count == 0
        assert runner.run_complexity(target="").violation_count == 0

    def test_todays_finding_is_counted(
        self, tmp_path: Path, runner_cls: type, marker: str, report_parts: tuple, tool: str
    ) -> None:
        (tmp_path / marker).touch()
        report = tmp_path.joinpath(*report_parts)
        executor = _writes_report(report, _ONE_FINDING_SARIF, exit_code=1, stdout="violations")

        result = runner_cls(cwd=tmp_path, executor=executor).run_linter(target="")

        assert [(e.file, e.line, e.code) for e in result.errors] == [
            ("src/A.java", 3, "UnusedImport")
        ]


# ---------------------------------------------------------------------------
# Rust: S10, S11
# ---------------------------------------------------------------------------

_CLIPPY_PARTIAL = json.dumps({"reason": "compiler-artifact", "target": {"name": "app"}})


class TestRust:
    def test_clippy_that_timed_out_did_not_run(self, tmp_path: Path) -> None:
        runner = RustRunner(
            cwd=tmp_path, executor=_executor(stdout=_CLIPPY_PARTIAL, timed_out=True)
        )

        _assert_lint_did_not_run(runner.run_linter(target=""), "cargo clippy", "timed out")
        _assert_complexity_did_not_run(
            runner.run_complexity(target=""), "cargo clippy", "timed out"
        )

    def test_clippy_that_raised_did_not_run(self, tmp_path: Path) -> None:
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.side_effect = RuntimeError("sandbox fell over")

        result = RustRunner(cwd=tmp_path, executor=executor).run_complexity(target="")

        _assert_complexity_did_not_run(result, "cargo clippy", "sandbox fell over")

    def test_clippy_with_no_findings_is_clean(self, tmp_path: Path) -> None:
        runner = RustRunner(cwd=tmp_path, executor=_executor(stdout=_CLIPPY_PARTIAL))

        assert runner.run_linter(target="").error_count == 0
        assert runner.run_complexity(target="").violation_count == 0


# ---------------------------------------------------------------------------
# TypeScript: S7
# ---------------------------------------------------------------------------


class TestTypeScript:
    def test_complexity_is_not_built_and_says_so(self, tmp_path: Path) -> None:
        executor = MagicMock(spec=SubprocessExecutor)

        result = TypeScriptRunner(cwd=tmp_path, executor=executor).run_complexity(
            target="src/", max_complexity=8
        )

        _assert_complexity_did_not_run(result, "TypeScript complexity checks are not implemented")
        assert result.max_complexity == 8
        executor.execute.assert_not_called()
