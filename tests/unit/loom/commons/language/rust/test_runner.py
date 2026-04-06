# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for RustRunner."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.loom.commons.language.rust.runner import RustRunner


class TestRustRunner:
    def test_run_compiler_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        runner = RustRunner(cwd=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="Compiling", stderr="")
            result = runner.run_compiler(target="src/")

            mock_run.assert_called_once()
            assert "cargo" in mock_run.call_args[0][0]
            assert "build" in mock_run.call_args[0][0]
            assert result.error_count == 0

    def test_run_tests_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        runner = RustRunner(cwd=tmp_path)

        with patch("subprocess.run") as mock_run:
            # First call for `cargo test`, second for `cargo2junit`
            mock_test_process = MagicMock(
                returncode=0, stdout='{"type":"test","event":"ok"}', stderr=""
            )
            mock_junit_process = MagicMock(
                returncode=0, stdout="<testsuites></testsuites>", stderr=""
            )
            mock_run.side_effect = [mock_test_process, mock_junit_process]

            with patch("junitparser.JUnitXml.fromstring") as mock_fromstring:
                mock_fromstring.return_value = []
                result = runner.run_tests(target="src/")

                assert mock_run.call_count == 2

                # Verify first `cargo test` call
                assert "cargo" in mock_run.call_args_list[0][0][0]
                assert "test" in mock_run.call_args_list[0][0][0]
                assert "--format=json" in mock_run.call_args_list[0][0][0]

                # Verify second `cargo2junit` call
                assert "cargo2junit" in mock_run.call_args_list[1][0][0]
                assert (
                    mock_run.call_args_list[1].kwargs.get("input") == '{"type":"test","event":"ok"}'
                )

                assert result.passed == 0
                assert result.failed == 0

    def test_run_linter_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        runner = RustRunner(cwd=tmp_path)

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

        with patch("subprocess.run") as mock_run:
            # First call `cargo clippy`, second `clippy-sarif`
            mock_clippy_process = MagicMock(
                returncode=0, stdout='{"reason":"compiler-message"}', stderr=""
            )
            mock_sarif_process = MagicMock(returncode=0, stdout=sarif_output, stderr="")
            mock_run.side_effect = [mock_clippy_process, mock_sarif_process]

            result = runner.run_linter(target="src/")

            assert mock_run.call_count == 2

            # Cargo clippy call
            assert "cargo" in mock_run.call_args_list[0][0][0]
            assert "clippy" in mock_run.call_args_list[0][0][0]
            assert "--message-format=json" in mock_run.call_args_list[0][0][0]

            # clippy-sarif call
            assert "clippy-sarif" in mock_run.call_args_list[1][0][0]
            assert mock_run.call_args_list[1].kwargs.get("input") == '{"reason":"compiler-message"}'

            assert result.error_count == 1
            assert result.errors[0].message == "A clippy error"
            assert result.errors[0].file == "src/main.rs"
            assert result.errors[0].line == 42

    def test_run_complexity_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        runner = RustRunner(cwd=tmp_path)

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

        with patch("subprocess.run") as mock_run:
            mock_clippy_process = MagicMock(returncode=0, stdout="", stderr="")
            mock_sarif_process = MagicMock(returncode=0, stdout=sarif_output, stderr="")
            mock_run.side_effect = [mock_clippy_process, mock_sarif_process]

            result = runner.run_complexity(target="src/", max_complexity=10)

            assert mock_run.call_count == 2
            assert "-W" in mock_run.call_args_list[0][0][0]
            assert "clippy::cognitive_complexity" in mock_run.call_args_list[0][0][0]

            assert result.violation_count == 1
            assert result.violations[0].complexity == 15
            assert result.violations[0].file == "src/main.rs"

    def test_run_debugger_success(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("")
        runner = RustRunner(cwd=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="DEBUG OK", stderr="")
            result = runner.run_debugger(target="src/", entrypoint="src/main.rs")

            mock_run.assert_called_once()
            assert "cargo" in mock_run.call_args[0][0]
            assert "run" in mock_run.call_args[0][0]
            assert result.exit_code == 0
            assert result.events[0].output == "DEBUG OK"
