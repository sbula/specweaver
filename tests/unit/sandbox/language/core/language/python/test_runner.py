# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for PythonQARunner."""

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
        mock_executor.execute.return_value = _make_result(
            exit_code=1, stdout='{"error": "fatal"}'
        )
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
# INT-US-09 SF-01 T9: container-mode integration
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

    def test_run_tests_engine_unavailable_becomes_synthetic_failure(
        self, tmp_path: Path
    ) -> None:
        from specweaver.sandbox.execution.container_executor import ContainerEngineUnavailableError

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = ContainerEngineUnavailableError("no engine")
        runner = PythonQARunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_tests(target="tests/")

        assert result.errors == 1
        assert result.failures[0].nodeid == "<sandbox>"
        assert "no engine" in result.failures[0].message

    def test_run_linter_engine_unavailable_becomes_synthetic_failure(
        self, tmp_path: Path
    ) -> None:
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
    """INT-US-09 SF-01 Red/Blue fix: sys.executable is the HOST interpreter path,
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
