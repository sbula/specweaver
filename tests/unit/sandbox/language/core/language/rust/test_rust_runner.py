# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Rust QA runner: one command per intent, and the parsing of what comes back.

Proves: D-VAL-03 FR-4

Cited under `specweaver-dev` §3.2c, from `INT-US-03-SF01-MIG`. Mutant: `cargo build` replaced by `cargo check`, which type-checks without producing artefacts — 1 fails.
The distinction matters: a `check` that passes is not a build that succeeded.

Every runner is exercised against a mocked executor, so what these tests pin is the *command* and the
*parse* — which is the whole of the contract at this tier. Whether the toolchain exists on the host is
a container concern, and `INT-US-09-SF01-MIG` holds it.
"""

from pathlib import Path
from unittest.mock import MagicMock

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.rust.runner import RustRunner


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


class TestRustRunner:
    def test_run_compiler_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=0, stdout="Compiling")
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")

        mock_executor.execute.assert_called_once()
        assert "cargo" in mock_executor.execute.call_args[0][0]
        assert "build" in mock_executor.execute.call_args[0][0]
        assert result.error_count == 0

    def test_run_tests_success(self, tmp_path: Path) -> None:
        """Cargo's own stable output, and the command it accepts.

        This test previously asserted `--format=json` was in the argv and fed the runner JUnit XML
        through a mocked `cargo2junit`. Both were fictions: real cargo rejects the flag outright, its
        JSON format is nightly-only, and `cargo2junit` was never installed. The mock made a broken
        command look proven — so the sample below is copied from a real `cargo test` run.
        """
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0,
            stdout=(
                "\nrunning 1 test\ntest t::works ... ok\n\n"
                "test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out;"
                " finished in 0.00s\n"
            ),
        )
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_tests(target="src/")

        argv = mock_executor.execute.call_args_list[0][0][0]
        assert argv[:2] == ["cargo", "test"], argv
        assert not any(a.startswith("--format") for a in argv), (
            f"`--format` is a libtest flag; cargo rejects it as an argument of its own: {argv}"
        )
        assert result.passed == 1
        assert result.failed == 0
        assert mock_executor.execute.call_count == 1, (
            "the second call was a pipe into `cargo2junit`, which is installed nowhere"
        )

    def test_run_linter_success(self, tmp_path: Path) -> None:
        """Clippy's own JSON, which is what the runner reads.

        This fed SARIF through a mocked `clippy-sarif`. That binary is installed nowhere, so in a
        real run the pipe produced nothing and the guard around it returned `error_count=0` — a
        clean verdict for code clippy had flagged. The sample is copied from a real clippy run.
        """
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0,
            stdout=(
                '{"reason":"compiler-message","message":{"level":"warning",'
                '"message":"unneeded `return` statement",'
                '"code":{"code":"clippy::needless_return"},'
                '"spans":[{"file_name":"src/lib.rs","line_start":3}]}}\n'
                # A complexity finding in the same stream: `run_complexity` reports these, so
                # counting them here would report every one of them twice.
                '{"reason":"compiler-message","message":{"level":"warning",'
                '"message":"the function has a cognitive complexity of (30/25)",'
                '"code":{"code":"clippy::cognitive_complexity"},'
                '"spans":[{"file_name":"src/lib.rs","line_start":9}]}}\n'
            ),
        )
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_linter(target="src/")

        assert result.error_count == 1, result
        assert result.errors[0].code == "clippy::needless_return"
        assert result.errors[0].line == 3
        assert mock_executor.execute.call_count == 1, (
            "the second call was a pipe into `clippy-sarif`, which is installed nowhere"
        )

    def test_run_complexity_success(self, tmp_path: Path) -> None:
        """Only the complexity lint, so a finding is not counted by both surfaces."""
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0,
            stdout=(
                '{"reason":"compiler-message","message":{"level":"warning",'
                '"message":"the function has a cognitive complexity of (11/10)",'
                '"code":{"code":"clippy::cognitive_complexity"},'
                '"spans":[{"file_name":"src/lib.rs","line_start":9}]}}\n'
                '{"reason":"compiler-message","message":{"level":"warning",'
                '"message":"unneeded `return` statement",'
                '"code":{"code":"clippy::needless_return"},'
                '"spans":[{"file_name":"src/lib.rs","line_start":3}]}}\n'
            ),
        )
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_complexity(target="src/")

        assert result.violation_count == 1, result
        assert "cognitive_complexity" in result.violations[0].function

    def test_run_debugger_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(exit_code=0, stdout="DEBUG OK")
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target="src/", entrypoint="src/main.rs")

        mock_executor.execute.assert_called_once()
        assert "cargo" in mock_executor.execute.call_args[0][0]
        assert "run" in mock_executor.execute.call_args[0][0]
        assert result.exit_code == 0
        assert result.events[0].output == "DEBUG OK"

    def test_run_compiler_failure(self, tmp_path: Path) -> None:
        """G-1: run_compiler with exit_code != 0 returns error count > 0."""
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = Exception("cargo build failed")
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")

        mock_executor.execute.assert_called_once()
        assert result.error_count == 1
        assert len(result.errors) == 1
        assert "cargo build failed" in result.errors[0].message

    def test_run_debugger_exception(self, tmp_path: Path) -> None:
        """G-2: run_debugger exception returns exit_code=1 with empty events."""
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.side_effect = Exception("process crashed")
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target="src/", entrypoint="src/main.rs")

        assert result.exit_code == 1
        assert result.duration_seconds == 0.0
        assert result.events == []

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = RustRunner(cwd=tmp_path)
        assert runner.language_name == "rust"
