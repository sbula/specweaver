# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for PythonQARunner."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.loom.commons.qa_runner.python.runner import PythonQARunner


class TestPythonQARunner:
    def test_run_compiler_stub(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        result = runner.run_compiler(target="src/")

        assert result.error_count == 0
        assert result.warning_count == 0
        assert len(result.errors) == 0

    def test_run_debugger_success(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="App started\nProcessing...",
                stderr="Warning: deprecated",
            )

            result = runner.run_debugger(target=".", entrypoint="src/main.py")

            mock_run.assert_called_once()
            assert result.exit_code == 1
            assert len(result.events) == 3
            assert result.events[0].category == "stdout"
            assert result.events[0].output == "App started"
            assert result.events[1].category == "stdout"
            assert result.events[1].output == "Processing..."
            assert result.events[2].category == "stderr"
            assert result.events[2].output == "Warning: deprecated"

    def test_run_debugger_timeout(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python"], timeout=300)

            result = runner.run_debugger(target=".", entrypoint="src/main.py")

            assert result.exit_code == 124
            assert result.duration_seconds == 300.0
            assert len(result.events) == 1
            assert result.events[0].category == "stderr"
            assert "Timeout expired" in result.events[0].output

    def test_run_architecture_check_success(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")

            result = runner.run_architecture_check(target=".")

            mock_run.assert_called_once()
            assert result.violation_count == 0
            assert len(result.violations) == 0

    def test_run_architecture_check_violations(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        mock_stdout = """
        [
          {
            "Located": {
              "file_path": "src/bad.py",
              "line_number": 10,
              "details": {
                "Code": {
                  "UndeclaredDependency": {
                    "dependency": "specweaver.cli",
                    "usage_module": "specweaver.validation",
                    "definition_module": "specweaver.cli"
                  }
                }
              }
            }
          }
        ]
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout=mock_stdout)

            result = runner.run_architecture_check(target=".")

            mock_run.assert_called_once()
            assert result.violation_count == 1
            assert len(result.violations) == 1
            v = result.violations[0]
            assert v.file == "src/bad.py"
            assert v.code == "UndeclaredDependency"
            assert "specweaver.cli" in v.message
            assert "specweaver.validation" in v.message

    def test_run_architecture_check_no_config(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]")

            result = runner.run_architecture_check(target=".")

            mock_run.assert_called_once()
            assert result.violation_count == 0

    def test_run_architecture_check_timeout(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["tach"], timeout=60)

            result = runner.run_architecture_check(target=".")

            mock_run.assert_called_once()
            assert result.violation_count == 1
            assert result.violations[0].code == "TimeoutExpired"

    def test_run_architecture_check_file_not_found(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("No such file or directory: 'tach'")

            result = runner.run_architecture_check(target=".")

            mock_run.assert_called_once()
            assert result.violation_count == 1
            assert result.violations[0].code == "FileNotFoundError"

    def test_run_architecture_check_invalid_json(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="TypeError: 'dict' object is not..."
            )

            result = runner.run_architecture_check(target=".")

            mock_run.assert_called_once()
            assert result.violation_count == 1
            assert result.violations[0].code == "JSONDecodeError"

    def test_run_architecture_check_invalid_type(self, tmp_path: Path) -> None:
        runner = PythonQARunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout='{"error": "fatal"}')

            result = runner.run_architecture_check(target=".")

            mock_run.assert_called_once()
            assert result.violation_count == 1
            assert result.violations[0].code == "InvalidOutput"
