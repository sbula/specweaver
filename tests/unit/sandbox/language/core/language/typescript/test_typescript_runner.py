# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The TypeScript QA runner: one command per intent, and the parsing of what comes back.

Proves: D-VAL-03 FR-7
Proves: TECH-087 FR-15

Cited under `specweaver-dev` §3.2c, from `INT-US-03-SF01-MIG`. Mutant: `tsc --noEmit` with the flag dropped, so a type-check starts writing JavaScript into the project
under test — 1 fails.

Every runner is exercised against a mocked executor, so what these tests pin is the *command* and the
*parse* — which is the whole of the contract at this tier. Whether the toolchain exists on the host is
a container concern, and `INT-US-09-SF01-MIG` holds it.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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

    def test_a_missing_tsc_says_it_did_not_run(self, tmp_path: Path) -> None:
        # The real executor never raises for a missing binary: exit -1, the OSError in stderr.
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=-1, stderr="[Errno 2] No such file or directory: 'npx'"
        )
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")

        assert result.error_count == 1
        assert result.errors[0].code == "ToolchainUnavailable"
        assert result.errors[0].message == (
            "tsc did not run: [Errno 2] No such file or directory: 'npx'"
        )

    @pytest.mark.parametrize("stdout", ["", "src/a.ts(1,1): error TS2304: Cannot find name 'x'.\n"])
    def test_a_tsc_timeout_says_tsc_timed_out(self, tmp_path: Path, stdout: str) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=-1, stdout=stdout, timed_out=True, duration_seconds=120.0
        )
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="custom.ts")

        assert result.error_count == 1
        assert result.errors[0].code == "ToolchainUnavailable"
        assert result.errors[0].message == "tsc timed out after 120 s"

    @pytest.mark.parametrize(
        "stdout",
        [
            "",
            '[{"filePath": "src/a.ts", "messages": [{"ruleId": "no-restricted-imports",'
            ' "message": "x", "line": 1}]}]',
        ],
    )
    def test_an_eslint_architecture_timeout_says_eslint_timed_out(
        self, tmp_path: Path, stdout: str
    ) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=-1, stdout=stdout, timed_out=True, duration_seconds=60.0
        )
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_architecture_check(target="src")

        assert result.violation_count == 1
        assert result.violations[0].code == "ToolchainUnavailable"
        assert result.violations[0].message == "ESLint timed out after 60 s"

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

            # Two calls now, and deliberately: the runner asks node whether it strips types
            # before deciding it needs a wrapper at all. Asserting the LAST call keeps the subject
            # of this test the fallback choice rather than the call count.
            probe_args = mock_executor.execute.call_args_list[0][0][0]
            assert probe_args[1] == "--version", probe_args

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
        # The real executor never raises for a missing binary: exit -1, the OSError in stderr.
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=-1, stderr="[Errno 2] No such file or directory: 'node'"
        )
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="src/index.js")
        assert result.exit_code == -1
        assert [e.output for e in result.events] == ["[Errno 2] No such file or directory: 'node'"]

    @pytest.mark.parametrize("stdout", ["", "started\n"])
    def test_a_debugger_timeout_says_the_program_timed_out(
        self, tmp_path: Path, stdout: str
    ) -> None:
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=-1, stdout=stdout, timed_out=True, duration_seconds=300.0
        )
        runner = TypeScriptRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target=".", entrypoint="src/index.ts")
        assert result.exit_code == 124
        assert [e.output for e in result.events] == ["src/index.ts timed out after 300 s"]

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = TypeScriptRunner(cwd=tmp_path, executor=SubprocessExecutor(cwd=tmp_path))
        assert runner.language_name == "typescript"
