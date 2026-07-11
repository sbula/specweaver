# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for RustRunner."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        # First call for `cargo test`, second for `cargo2junit`
        mock_executor.execute.side_effect = [
            _make_result(exit_code=0, stdout='{"type":"test","event":"ok"}'),
            _make_result(exit_code=0, stdout="<testsuites></testsuites>"),
        ]
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        with patch("junitparser.JUnitXml.fromstring") as mock_fromstring:
            mock_fromstring.return_value = []
            result = runner.run_tests(target="src/")

            assert mock_executor.execute.call_count == 2

            # Verify first `cargo test` call
            assert "cargo" in mock_executor.execute.call_args_list[0][0][0]
            assert "test" in mock_executor.execute.call_args_list[0][0][0]
            assert "--format=json" in mock_executor.execute.call_args_list[0][0][0]

            # Verify second `cargo2junit` call
            assert "cargo2junit" in mock_executor.execute.call_args_list[1][0][0]
            assert (
                mock_executor.execute.call_args_list[1].kwargs.get("input_text")
                == '{"type":"test","event":"ok"}'
            )

            assert result.passed == 0
            assert result.failed == 0

    def test_run_linter_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)

        sarif_output = json.dumps(
            {
                "runs": [
                    {
                        "results": [
                            {
                                "message": {"text": "A clippy error"},
                                "locations": [
                                    {
                                        "physicalLocation": {
                                            "artifactLocation": {"uri": "src/main.rs"},
                                            "region": {"startLine": 42},
                                        }
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        )

        # First call `cargo clippy`, second `clippy-sarif`
        mock_executor.execute.side_effect = [
            _make_result(exit_code=0, stdout='{"reason":"compiler-message"}'),
            _make_result(exit_code=0, stdout=sarif_output),
        ]
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_linter(target="src/")

        assert mock_executor.execute.call_count == 2

        # Cargo clippy call
        assert "cargo" in mock_executor.execute.call_args_list[0][0][0]
        assert "clippy" in mock_executor.execute.call_args_list[0][0][0]
        assert "--message-format=json" in mock_executor.execute.call_args_list[0][0][0]

        # clippy-sarif call
        assert "clippy-sarif" in mock_executor.execute.call_args_list[1][0][0]
        assert (
            mock_executor.execute.call_args_list[1].kwargs.get("input_text")
            == '{"reason":"compiler-message"}'
        )

        assert result.error_count == 1
        assert result.errors[0].message == "A clippy error"
        assert result.errors[0].file == "src/main.rs"
        assert result.errors[0].line == 42

    def test_run_complexity_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)

        # Mock clippy-sarif output containing a cognitive complexity error
        sarif_output = json.dumps(
            {
                "runs": [
                    {
                        "results": [
                            {
                                "ruleId": "clippy::cognitive_complexity",
                                "properties": {"complexity": 15},
                                "message": {
                                    "text": "The function `complex_fn` has a cognitive complexity of 15"
                                },
                                "locations": [
                                    {
                                        "physicalLocation": {
                                            "artifactLocation": {"uri": "src/main.rs"},
                                            "region": {"startLine": 100},
                                        }
                                    }
                                ],
                            }
                        ]
                    }
                ]
            }
        )

        mock_executor.execute.side_effect = [
            _make_result(exit_code=0, stdout=""),
            _make_result(exit_code=0, stdout=sarif_output),
        ]
        runner = RustRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_complexity(target="src/", max_complexity=10)

        assert mock_executor.execute.call_count == 2
        assert "-W" in mock_executor.execute.call_args_list[0][0][0]
        assert "clippy::cognitive_complexity" in mock_executor.execute.call_args_list[0][0][0]

        assert result.violation_count == 1
        assert result.violations[0].complexity == 15
        assert result.violations[0].file == "src/main.rs"

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

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = RustRunner(cwd=tmp_path)
        assert runner.language_name == "rust"
