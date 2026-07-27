# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for KotlinRunner — SubprocessExecutor migration."""

import json
from pathlib import Path
from unittest.mock import MagicMock

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner


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


class TestKotlinRunner:
    def test_run_compiler_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").touch()
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESSFUL"
        )
        runner = KotlinRunner(cwd=tmp_path, executor=mock_executor)

        res = runner.run_compiler(target="")

        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        cmd = call_args[0][0]
        assert "compileKotlin" in cmd
        assert res.error_count == 0

    def test_run_compiler_failure(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").touch()
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=1, stdout="", stderr="COMPILATION ERROR"
        )
        runner = KotlinRunner(cwd=tmp_path, executor=mock_executor)

        res = runner.run_compiler(target="")
        assert res.error_count == 1
        assert res.errors[0].code == "COMPILE_ERROR"

    def test_run_tests_wipes_stale_xml(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").touch()
        build_dir = tmp_path / "build" / "test-results"
        build_dir.mkdir(parents=True)
        stale_xml = build_dir / "TEST-stale.xml"
        stale_xml.touch()

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESSFUL"
        )
        runner = KotlinRunner(cwd=tmp_path, executor=mock_executor)

        res = runner.run_tests(target="")
        assert not stale_xml.exists()
        assert res.total >= 0
        mock_executor.execute.assert_called_once()

    def test_run_linter_detekt_sarif(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").touch()

        report_dir = tmp_path / "build" / "reports" / "detekt"
        report_dir.mkdir(parents=True, exist_ok=True)
        sarif_file = report_dir / "detekt.sarif"

        mock_sarif = {
            "runs": [
                {
                    "results": [
                        {
                            "ruleId": "EmptyFunctionBlock",
                            "message": {"text": "This block is empty."},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "src/main/kotlin/App.kt"},
                                        "region": {"startLine": 10, "startColumn": 5},
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        sarif_file.write_text(json.dumps(mock_sarif), "utf-8")

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result()
        runner = KotlinRunner(cwd=tmp_path, executor=mock_executor)

        res = runner.run_linter(target="")

        mock_executor.execute.assert_called_once()
        assert res.error_count == 1
        assert res.errors[0].message == "This block is empty."
        assert res.errors[0].line == 10
        assert res.errors[0].file == "src/main/kotlin/App.kt"

    def test_run_complexity_detekt_sarif(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").touch()

        report_dir = tmp_path / "build" / "reports" / "detekt"
        report_dir.mkdir(parents=True, exist_ok=True)
        sarif_file = report_dir / "detekt.sarif"

        mock_sarif = {
            "runs": [
                {
                    "results": [
                        {
                            "ruleId": "ComplexMethod",
                            "properties": {"complexity": 15},
                            "message": {
                                "text": "The function complexLogic appears to be too complex (15)."
                            },
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "App.kt"},
                                        "region": {"startLine": 20},
                                    }
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        sarif_file.write_text(json.dumps(mock_sarif), "utf-8")

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result()
        runner = KotlinRunner(cwd=tmp_path, executor=mock_executor)

        res = runner.run_complexity(target="")

        mock_executor.execute.assert_called_once()
        assert res.violation_count == 1
        assert res.violations[0].complexity == 15
        assert res.violations[0].line == 20

    def test_run_debugger(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").touch()
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0,
            stdout="Listening for transport dt_socket at address: 5005\nTest JVM Output",
        )
        runner = KotlinRunner(cwd=tmp_path, executor=mock_executor)

        res = runner.run_debugger(target="", entrypoint="AppKt")

        mock_executor.execute.assert_called_once()
        assert res.exit_code == 0
        assert len(res.events) > 0

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = KotlinRunner(cwd=tmp_path)
        assert runner.language_name == "kotlin"
