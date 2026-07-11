# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for TypeScriptRunner execution."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner


def _make_result(
    exit_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    duration_seconds: float = 0.01,
) -> SubprocessResult:
    return SubprocessResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        duration_seconds=duration_seconds,
    )


class TestTypeScriptRunner:
    def test_run_compiler_success(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=0, stdout="No errors")
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")

        mock_executor.execute.assert_called_once()
        assert "tsc" in mock_executor.execute.call_args[0][0]
        assert "--noEmit" in mock_executor.execute.call_args[0][0]
        assert result.error_count == 0
        assert not result.errors

    def test_run_compiler_missing_binary(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = FileNotFoundError()
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")
        assert result.error_count == 1
        assert result.errors[0].code == "ENOENT"

    def test_run_compiler_timeout(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(timed_out=True, duration_seconds=120.0)
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="custom.ts")
        assert result.error_count == 1
        assert result.errors[0].code == "TIMEOUT"

    def test_run_debugger_parsing(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        with patch("shutil.which") as mock_which:
            # Simulate tsx available on PATH
            mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd != "npx" else None
            mock_executor.execute.return_value = _make_result(
                exit_code=1,
                stdout="App started\nProcessing...",
                stderr="Warning: deprecated",
            )
            runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

            result = runner.run_debugger(target=".", entrypoint="src/index.ts")

            mock_executor.execute.assert_called_once()
            cmd_args = mock_executor.execute.call_args[0][0]
            # tsx is preferred over ts-node when available
            assert any("tsx" in str(arg) for arg in cmd_args), (
                f"Expected 'tsx' in command, got {cmd_args}"
            )

            assert result.exit_code == 1
            assert len(result.events) == 3
            events = result.events

            assert events[0].category == "stdout"
            assert events[0].output == "App started"
            assert events[1].category == "stdout"
            assert events[1].output == "Processing..."
            assert events[2].category == "stderr"
            assert events[2].output == "Warning: deprecated"

    def test_run_debugger_ts_node_fallback(self, tmp_path: Path) -> None:
        """When tsx is not installed, falls back to ts-node via npx."""
        mock_executor = MagicMock(spec=SubprocessExecutor)
        with patch("shutil.which") as mock_which:
            # tsx NOT on PATH, npx IS
            mock_which.side_effect = lambda cmd: "/usr/bin/npx" if cmd == "npx" else None
            mock_executor.execute.return_value = _make_result(exit_code=0, stdout="OK")
            runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

            result = runner.run_debugger(target=".", entrypoint="src/index.ts")

            mock_executor.execute.assert_called_once()
            cmd_args = mock_executor.execute.call_args[0][0]
            assert "ts-node" in cmd_args, f"Expected 'ts-node' fallback, got {cmd_args}"
            assert result.exit_code == 0

    def test_run_debugger_js_fallback(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=0, stdout="JS started")
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="dist/index.js")

        mock_executor.execute.assert_called_once()
        # Assert "node" is used instead of "ts-node"
        cmd_args = mock_executor.execute.call_args[0][0]
        assert any("node" in str(arg).lower() for arg in cmd_args), (
            f"Could not find 'node' in {cmd_args}"
        )
        assert not any("ts-node" in str(arg).lower() for arg in cmd_args), (
            f"Found 'ts-node' in {cmd_args}"
        )

        assert result.exit_code == 0
        assert len(result.events) == 1
        assert result.events[0].output == "JS started"

    def test_run_debugger_missing_binary(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = FileNotFoundError()
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="src/index.ts")
        assert result.exit_code == 127
        assert len(result.events) == 1
        assert "not found" in result.events[0].output

    def test_run_debugger_timeout(self, tmp_path: Path) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(timed_out=True, duration_seconds=300.0)
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="src/index.ts")
        assert result.exit_code == 124
        assert "Timeout" in result.events[0].output

    def test_run_tests_stub(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        result = runner.run_tests(target="src/")
        assert result.total == 0
        assert result.errors == 0
        assert result.failed == 0

    def test_run_linter_stub(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        result = runner.run_linter(target="src/")
        assert result.error_count == 0

    def test_run_complexity_stub(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        result = runner.run_complexity(target="src/")
        assert result.violation_count == 0

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        assert runner.language_name == "typescript"
