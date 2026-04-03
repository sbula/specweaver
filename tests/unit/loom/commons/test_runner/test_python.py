# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for PythonTestRunner."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.loom.commons.test_runner.python import PythonTestRunner

class TestPythonTestRunner:
    def test_run_compiler_stub(self, tmp_path: Path) -> None:
        runner = PythonTestRunner(cwd=tmp_path)
        result = runner.run_compiler(target="src/")
        
        assert result.error_count == 0
        assert result.warning_count == 0
        assert len(result.errors) == 0

    def test_run_debugger_success(self, tmp_path: Path) -> None:
        runner = PythonTestRunner(cwd=tmp_path)
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
        runner = PythonTestRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd=["python"], timeout=300)
            
            result = runner.run_debugger(target=".", entrypoint="src/main.py")
            
            assert result.exit_code == 124
            assert result.duration_seconds == 300.0
            assert len(result.events) == 1
            assert result.events[0].category == "stderr"
            assert "Timeout expired" in result.events[0].output
