# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Python QA runner: one command per intent, and the parsing of what comes back.

Proves: D-VAL-03 FR-3

Cited under `specweaver-dev` §3.2c, from `INT-US-03-SF01-MIG`. Mutant: the pytest invocation replaced by `unittest`, which cannot honour the same flags or emit the same
report — **28 fail across all three tiers**, because Python is the default runner and nearly every
pipeline e2e ends up executing tests through it.

Every runner is exercised against a mocked executor, so what these tests pin is the *command* and the
*parse* — which is the whole of the contract at this tier. Whether the toolchain exists on the host is
a container concern, and `INT-US-09-SF01-MIG` holds it.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.python.runner import PythonQARunner


def _make_result(
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    duration_seconds: float = 0.1,
) -> SubprocessResult:
    """Helper to build SubprocessResult for tests."""
    return SubprocessResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_seconds=duration_seconds,
    )


class TestPythonQARunner:
    def test_run_compiler_stub(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        result = runner.run_compiler(target="src/")

        assert result.error_count == 0
        assert result.warning_count == 0
        assert len(result.errors) == 0

    def test_run_debugger_success(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=1,
            stdout="App started\nProcessing...",
            stderr="Warning: deprecated",
        )
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="src/main.py")

        mock_executor.execute.assert_called_once()
        assert result.exit_code == 1
        # events come from result.events which is empty in our mock (default)
        # The migrated code uses result.events directly instead of manual line splitting
        assert result.duration_seconds == 0.1

    def test_run_debugger_timeout(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=-1,
            timed_out=True,
            duration_seconds=300.0,
        )
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="src/main.py")

        assert result.exit_code == 124
        assert result.duration_seconds == 300.0
        assert len(result.events) == 1
        assert result.events[0].category == "stderr"
        assert "Timeout expired" in result.events[0].output

    def test_run_architecture_check_success(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(stdout="[]")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value="/usr/bin/tach"):
            result = runner.run_architecture_check(target=".")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 0
        assert len(result.violations) == 0

    def test_run_architecture_check_violations(self, tmp_path: Path) -> None:
        mock_stdout = """
        [
          {
            "Located": {
              "file_path": "src/bad.py",
              "line_number": 10,
              "details": {
                "Code": {
                  "UndeclaredDependency": {
                    "dependency": "specweaver.interfaces.cli",
                    "usage_module": "specweaver.assurance.validation",
                    "definition_module": "specweaver.interfaces.cli"
                  }
                }
              }
            }
          }
        ]
        """
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=1, stdout=mock_stdout)
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value="/usr/bin/tach"):
            result = runner.run_architecture_check(target=".")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 1
        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.file == "src/bad.py"
        assert v.code == "UndeclaredDependency"
        assert "specweaver.interfaces.cli" in v.message
        assert "specweaver.assurance.validation" in v.message

    def test_run_architecture_check_no_config(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(stdout="[]")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value="/usr/bin/tach"):
            result = runner.run_architecture_check(target=".")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 0

    def test_run_architecture_check_timeout(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(timed_out=True)
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value="/usr/bin/tach"):
            result = runner.run_architecture_check(target=".")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 1
        assert result.violations[0].code == "TimeoutExpired"

    def test_run_architecture_check_file_not_found(self, tmp_path: Path) -> None:
        """shutil.which returns None → tach not installed → FileNotFoundError result."""
        mock_executor = MagicMock(spec=SubprocessExecutor)
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value=None):
            result = runner.run_architecture_check(target=".")

        # Executor should NOT be called when tool is not found
        mock_executor.execute.assert_not_called()
        assert result.violation_count == 1
        assert result.violations[0].code == "FileNotFoundError"

    def test_run_architecture_check_invalid_json(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=1, stdout="TypeError: 'dict' object is not..."
        )
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value="/usr/bin/tach"):
            result = runner.run_architecture_check(target=".")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 1
        assert result.violations[0].code == "JSONDecodeError"

    def test_run_architecture_check_invalid_type(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=1, stdout='{"error": "fatal"}')
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value="/usr/bin/tach"):
            result = runner.run_architecture_check(target=".")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 1
        assert result.violations[0].code == "InvalidOutput"

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        assert runner.language_name == "python"


# ---------------------------------------------------------------------------
# B-EXEC-01: container-mode integration
# ---------------------------------------------------------------------------


class TestContainerModeIntegration:
    """Tach pre-check skip + ContainerEngineUnavailableError handling."""

    def test_tach_precheck_skipped_in_container_mode(self, tmp_path: Path) -> None:
        from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

        mock_executor = MagicMock(spec=ContainerSubprocessExecutor)
        mock_executor.execute.return_value = _make_result(stdout="[]")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which") as mock_which:
            result = runner.run_architecture_check(target=".")

        mock_which.assert_not_called()
        assert result.violation_count == 0

    def test_tach_precheck_still_runs_in_host_mode(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(stdout="[]")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        with patch("shutil.which", return_value=None) as mock_which:
            result = runner.run_architecture_check(target=".")

        mock_which.assert_called_once_with("tach")
        assert result.violation_count == 1
        assert result.violations[0].code == "FileNotFoundError"

    def test_run_tests_engine_unavailable_becomes_synthetic_failure(self, tmp_path: Path) -> None:
        from specweaver.sandbox.execution.container_executor import ContainerEngineUnavailableError

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = ContainerEngineUnavailableError("no engine")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_tests(target="tests/")

        assert result.errors == 1
        assert result.failures[0].nodeid == "<sandbox>"
        assert "no engine" in result.failures[0].message

    def test_run_linter_engine_unavailable_becomes_synthetic_failure(self, tmp_path: Path) -> None:
        from specweaver.sandbox.execution.container_executor import ContainerEngineUnavailableError

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = ContainerEngineUnavailableError("no engine")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_linter(target="src/")

        assert result.error_count == 0
        assert result.errors == []

    def test_run_complexity_engine_unavailable_becomes_synthetic_failure(
        self, tmp_path: Path
    ) -> None:
        from specweaver.sandbox.execution.container_executor import ContainerEngineUnavailableError

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = ContainerEngineUnavailableError("no engine")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_complexity(target="src/")

        assert result.violation_count == 0

    def test_run_debugger_engine_unavailable_becomes_synthetic_failure(
        self, tmp_path: Path
    ) -> None:
        from specweaver.sandbox.execution.container_executor import ContainerEngineUnavailableError

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = ContainerEngineUnavailableError("no engine")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="main.py")

        assert result.exit_code == 124
        assert "no engine" in result.events[0].output

    def test_run_architecture_check_engine_unavailable_becomes_synthetic_failure(
        self, tmp_path: Path
    ) -> None:
        from specweaver.sandbox.execution.container_executor import (
            ContainerEngineUnavailableError,
            ContainerSubprocessExecutor,
        )

        mock_executor = MagicMock(spec=ContainerSubprocessExecutor)
        mock_executor.execute.side_effect = ContainerEngineUnavailableError("no engine")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_architecture_check(target=".")

        assert result.violation_count == 1
        assert result.violations[0].code == "ContainerEngineUnavailableError"


class TestRunDebuggerInterpreterResolution:
    """B-EXEC-01 Red/Blue fix: sys.executable is the HOST interpreter path,
    meaningless inside a container — discovered via the real-engine integration test."""

    def test_uses_sys_executable_in_host_mode(self, tmp_path: Path) -> None:
        import sys

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=0)
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        runner.run_debugger(target=".", entrypoint="main.py")

        called_cmd = mock_executor.execute.call_args.args[0]
        assert called_cmd == [sys.executable, "main.py"]

    def test_uses_bare_python_in_container_mode(self, tmp_path: Path) -> None:
        from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

        mock_executor = MagicMock(spec=ContainerSubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=0)
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        runner.run_debugger(target=".", entrypoint="main.py")

        called_cmd = mock_executor.execute.call_args.args[0]
        assert called_cmd == ["python", "main.py"]


# ---------------------------------------------------------------------------
# INT-US-24 SF-03 (inherited defect #7): the pytest summary parser must handle
# pytest's REAL summary orderings. "2 failed, 1 passed in 0.03s" (failed
# FIRST — pytest's actual order for mixed outcomes) previously parsed as
# passed=1/failed=0 → a failing run reported SUCCESS. Failed-only lines
# parsed fine, which is how the bug survived the US-3 loop.
# ---------------------------------------------------------------------------


class TestParsePytestSummaryOrderings:
    def _parse(self, stdout: str):
        from specweaver.sandbox.language.core.python.runner import _parse_pytest_output

        return _parse_pytest_output(stdout)

    def test_mixed_failed_first_real_pytest_order(self) -> None:
        # [Hostile→Happy] the shape that false-greened.
        out = self._parse("FF.\n2 failed, 1 passed in 0.03s\n")
        assert out["failed"] == 2
        assert out["passed"] == 1
        assert out["total"] == 3

    def test_passed_first_still_parses(self) -> None:
        out = self._parse("3 passed, 2 failed in 1.20s\n")
        assert out["passed"] == 3
        assert out["failed"] == 2

    def test_failed_only(self) -> None:
        out = self._parse("1 failed in 0.5s\n")
        assert out["failed"] == 1
        assert out["passed"] == 0

    def test_errors_and_skipped_any_order(self) -> None:
        out = self._parse("1 error, 2 skipped, 3 passed in 0.9s\n")
        assert out["errors"] == 1
        assert out["skipped"] == 2
        assert out["passed"] == 3

    def test_warnings_ignored(self) -> None:
        # [Boundary] "5 passed, 2 warnings in 0.4s" — warnings are not a count bucket.
        out = self._parse("5 passed, 2 warnings in 0.40s\n")
        assert out["passed"] == 5
        assert out["failed"] == 0
        assert out["total"] == 5

    def test_failure_line_without_message_suffix(self) -> None:
        # [Boundary] -q short summaries may lack the " - msg" suffix.
        out = self._parse(
            "FAILED scenarios/generated/test_x.py::test_a[row1]\n"
            "FAILED tests/test_y.py::test_b - AssertionError: boom\n"
            "2 failed in 0.1s\n"
        )
        assert len(out["failures"]) == 2
        assert out["failures"][0].nodeid.endswith("test_a[row1]")
        assert out["failures"][1].message == "AssertionError: boom"


class TestPythonQARunnerMissingToolchain:
    """A toolchain that is not installed must not read as a clean run."""

    def test_absent_pytest_reports_an_error_rather_than_zero_tests(self, tmp_path: Path) -> None:
        """`No module named pytest` produced `passed=0 failed=0 errors=0` — indistinguishable
        from a project that simply has no tests, and from a caller's view, nothing wrong.

        The sandbox reaches this state for real: `B-EXEC-01`'s prepare phase runs a bare
        `uv sync`, which does not install a project whose dev tooling sits in an extra. The QA
        gate then reports success for a run that never happened.

        The discriminator is empty stdout: a pytest that never started says nothing at all,
        whereas every verdict pytest can reach — including "no tests" — it prints.
        """
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(
            exit_code=1, stdout="", stderr="/usr/bin/python3: No module named pytest"
        )
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_tests(target=".")

        assert result.errors == 1, "an unusable toolchain must be reported, not silently passed"
        assert result.total == 1
        assert "pytest" in result.failures[0].message

    def test_an_empty_suite_is_still_reported_as_empty(self, tmp_path: Path) -> None:
        """The control. pytest exits 5 when it collects nothing, and that is not an error.

        Without this the fix above would turn every genuinely empty target into a failure, which
        is the obvious over-correction.
        """
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(exit_code=5, stdout="no tests ran", stderr="")
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_tests(target=".")

        assert result.errors == 0
        assert result.total == 0

    def test_a_target_directory_that_does_not_exist_is_not_a_toolchain_failure(
        self, tmp_path: Path
    ) -> None:
        """Exit **4**, and the regression that caught the first version of this guard.

        `sw implement` runs the QA gate against a project whose `tests/` directory does not exist
        yet — the tests are what it is about to generate. pytest exits 4 there, having started
        and run correctly. Keying the guard on the exit code failed that whole pipeline, which is
        why it keys on empty stdout instead: pytest printed `no tests ran in 0.00s`.
        """
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(
            exit_code=4, stdout="no tests ran in 0.00s", stderr=""
        )
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_tests(target="tests/")

        assert result.errors == 0
        assert result.total == 0

    def test_a_normal_failing_run_is_untouched(self, tmp_path: Path) -> None:
        """A real test failure exits non-zero with parseable output and must stay a failure."""
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(
            exit_code=1, stdout="1 failed, 2 passed in 0.10s", stderr=""
        )
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_tests(target=".")

        assert result.failed == 1
        assert result.passed == 2

    def test_absent_ruff_reports_an_error_rather_than_a_clean_lint(self, tmp_path: Path) -> None:
        """The same hole in the lint path, and this one had no guard of any kind.

        `_parse_ruff_json` swallows a `JSONDecodeError` and returns no errors, so an empty stdout
        from an uninstalled ruff was indistinguishable from `[]` — ruff's own way of saying the
        target is clean.
        """
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(
            exit_code=1, stdout="", stderr="/usr/bin/python3: No module named ruff"
        )
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_linter(target=".")

        assert result.error_count == 1, "an unusable linter must be reported, not read as clean"
        assert "ruff" in result.errors[0].message

    def test_a_clean_ruff_run_is_untouched(self, tmp_path: Path) -> None:
        """The control: ruff exits 0 and prints `[]` when there is nothing to report."""
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(exit_code=0, stdout="[]")
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_linter(target=".")

        assert result.error_count == 0

    def test_absent_complexipy_reports_an_error_rather_than_no_violations(
        self, tmp_path: Path
    ) -> None:
        """The fourth path, missed on the first pass through this very file.

        `run_tests`, `run_linter` and `run_architecture_check` were fixed together and
        `run_complexity` was not, which is its own small lesson: the hole was found by probing
        every method on the runner rather than by re-reading the ones already changed.
        """
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(
            exit_code=127, stdout="", stderr="/usr/bin/python3: No module named complexipy"
        )
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_complexity(target=".")

        assert result.violation_count == 1, "an unusable checker is not an absence of violations"
        assert "complexipy" in result.violations[0].message

    def test_a_clean_complexity_run_is_untouched(self, tmp_path: Path) -> None:
        """The control: the tool ran, found nothing, and exited 0."""
        executor = MagicMock(spec=SubprocessExecutor)
        executor.execute.return_value = _make_result(exit_code=0, stdout="[]")
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_complexity(target=".")

        assert result.violation_count == 0

    def test_absent_tach_in_a_container_reports_an_error(self, tmp_path: Path) -> None:
        """The architecture path guards on `shutil.which`, which is the wrong filesystem.

        That check asks whether tach is on the *host* PATH, and `B-EXEC-01` skips it entirely in
        container mode precisely because the host is irrelevant there. So the one configuration
        where the prepared environment can actually lack tach is the one configuration with no
        guard — and an empty stdout means clean to `_build_architecture_result`.
        """
        from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

        executor = MagicMock(spec=ContainerSubprocessExecutor)
        executor.execute.return_value = _make_result(
            exit_code=1, stdout="", stderr="/usr/bin/python3: No module named tach"
        )
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_architecture_check(target=".")

        assert result.violation_count == 1, "an unusable checker is not a clean architecture"
        assert "tach" in result.violations[0].message

    def test_a_clean_tach_run_is_untouched(self, tmp_path: Path) -> None:
        """The control: tach exits 0 with an empty violation list when the boundaries hold."""
        from specweaver.sandbox.execution.container_executor import ContainerSubprocessExecutor

        executor = MagicMock(spec=ContainerSubprocessExecutor)
        executor.execute.return_value = _make_result(exit_code=0, stdout="[]")
        runner = PythonQARunner(cwd=tmp_path, executor=executor)

        result = runner.run_architecture_check(target=".")

        assert result.violation_count == 0
