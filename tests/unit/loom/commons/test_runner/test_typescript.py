# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for TypeScriptRunner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.loom.commons.test_runner.typescript import TypeScriptRunner


class TestTypeScriptRunner:
    def test_run_compiler_success(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="No errors", stderr="")
            result = runner.run_compiler(target="src/")

            mock_run.assert_called_once()
            assert "tsc" in mock_run.call_args[0][0]
            assert "--noEmit" in mock_run.call_args[0][0]
            assert result.error_count == 0
            assert not result.errors

    def test_run_compiler_regex_parsing(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            tsc_output = (
                "src/main.ts(12,5): error TS2322: Type 'string' is not assignable to type 'number'.\n"
                "lib/utils.ts(45,1): error TS1005: ',' expected.\n"
                "Other compilation error info without standard format.\n"
            )
            mock_run.return_value = MagicMock(returncode=2, stdout=tsc_output, stderr="")

            result = runner.run_compiler(target="src/")

            assert result.error_count == 2
            assert len(result.errors) == 2

            err1 = result.errors[0]
            assert err1.file == "src/main.ts"
            assert err1.line == 12
            assert err1.column == 5
            assert err1.message == "Type 'string' is not assignable to type 'number'."
            assert err1.code == "TS2322"
            assert not err1.is_warning

            err2 = result.errors[1]
            assert err2.file == "lib/utils.ts"
            assert err2.line == 45
            assert err2.column == 1

    def test_run_debugger_parsing(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="App started\nProcessing...",
                stderr="Warning: deprecated",
            )

            result = runner.run_debugger(target=".", entrypoint="src/index.ts")

            mock_run.assert_called_once()
            assert "ts-node" in mock_run.call_args[0][0]

            assert result.exit_code == 1
            assert len(result.events) == 3
            events = result.events

            assert events[0].category == "stdout"
            assert events[0].output == "App started"
            assert events[1].category == "stdout"
            assert events[1].output == "Processing..."
            assert events[2].category == "stderr"
            assert events[2].output == "Warning: deprecated"

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

    def test_run_compiler_missing_binary(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = runner.run_compiler(target="src/")
            assert result.error_count == 1
            assert result.errors[0].code == "ENOENT"

    def test_run_debugger_missing_binary(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = runner.run_debugger(target=".", entrypoint="src/index.ts")
            assert result.exit_code == 127
            assert len(result.events) == 1
            assert "not found" in result.events[0].output

    def test_run_compiler_timeout(self, tmp_path: Path) -> None:
        import subprocess

        runner = TypeScriptRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["npx"], timeout=120)
            result = runner.run_compiler(target="custom.ts")
            assert result.error_count == 1
            assert result.errors[0].code == "TIMEOUT"

    def test_run_debugger_timeout(self, tmp_path: Path) -> None:
        import subprocess

        runner = TypeScriptRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["npx"], timeout=300)
            result = runner.run_debugger(target=".", entrypoint="src/index.ts")
            assert result.exit_code == 124
            assert "Timeout" in result.events[0].output
