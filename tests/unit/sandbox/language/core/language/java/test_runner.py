# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for JavaRunner — SubprocessExecutor migration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import SubprocessResult
from specweaver.sandbox.language.core.java.runner import JavaRunner


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


class TestJavaRunner:
    def test_detects_gradle_over_maven(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        (tmp_path / "pom.xml").write_text("")

        runner = JavaRunner(cwd=tmp_path)
        assert runner._get_build_tool() == "gradle"

    def test_detects_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")

        runner = JavaRunner(cwd=tmp_path)
        assert runner._get_build_tool() == "maven"

    def test_run_compiler_gradle_success(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESSFUL", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")

        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        cmd = call_args[0][0]
        assert "compileJava" in cmd
        assert result.error_count == 0

    def test_run_compiler_maven_success(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESS", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")

        mock_executor.execute.assert_called_once()
        call_args = mock_executor.execute.call_args
        cmd = call_args[0][0]
        assert "compile" in cmd
        assert result.error_count == 0

    def test_run_compiler_failure(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=1, stdout="", stderr="COMPILATION ERROR"
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_compiler(target="src/")
        assert result.error_count == 1

    def test_run_tests_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")

        # Create a stale XML to verify it's cleared
        stale_xml = tmp_path / "build" / "test-results" / "test" / "TEST-stale.xml"
        stale_xml.parent.mkdir(parents=True, exist_ok=True)
        stale_xml.write_text("<testsuite><testcase name='failure'/></testsuite>")

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESSFUL", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        with patch("junitparser.JUnitXml.fromfile") as mock_fromfile:
            mock_fromfile.return_value = []
            result = runner.run_tests(target="src/")

            assert not stale_xml.exists(), "Stale XML was not cleared before running tests!"
            mock_executor.execute.assert_called_once()
            assert result.passed == 0
            assert result.failed == 0

    def test_run_tests_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")

        stale_xml = tmp_path / "target" / "surefire-reports" / "TEST-stale.xml"
        stale_xml.parent.mkdir(parents=True, exist_ok=True)
        stale_xml.write_text("<testsuite><testcase name='failure'/></testsuite>")

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESS", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        with patch("junitparser.JUnitXml.fromfile") as mock_fromfile:
            mock_fromfile.return_value = []
            result = runner.run_tests(target="src/")

            assert not stale_xml.exists(), "Stale XML was not cleared before running tests!"
            mock_executor.execute.assert_called_once()
            assert result.passed == 0
            assert result.failed == 0

    def test_run_linter_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")

        pmd_file = tmp_path / "build" / "reports" / "pmd" / "main.sarif"
        pmd_file.parent.mkdir(parents=True, exist_ok=True)
        pmd_file.write_text(
            '{"runs": [{"results": [{"message": {"text": "A lint error"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main/java/Main.java"}, "region": {"startLine": 10}}}]}]}]}'
        )

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESSFUL", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_linter(target="src/")

        mock_executor.execute.assert_called_once()
        assert result.error_count == 1
        assert result.errors[0].message == "A lint error"
        assert result.errors[0].file == "src/main/java/Main.java"
        assert result.errors[0].line == 10

    def test_run_linter_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")

        pmd_file = tmp_path / "target" / "pmd.sarif"
        pmd_file.parent.mkdir(parents=True, exist_ok=True)
        pmd_file.write_text(
            '{"runs": [{"results": [{"message": {"text": "A lint error"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main/java/Main.java"}, "region": {"startLine": 10}}}]}]}]}'
        )

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESS", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_linter(target="src/")

        mock_executor.execute.assert_called_once()
        assert result.error_count == 1
        assert result.errors[0].message == "A lint error"

    def test_run_complexity_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")

        pmd_file = tmp_path / "build" / "reports" / "pmd" / "main.sarif"
        pmd_file.parent.mkdir(parents=True, exist_ok=True)
        pmd_file.write_text(
            '{"runs": [{"results": [{"ruleId": "CyclomaticComplexity", "properties": {"complexity": 12}, "message": {"text": "The method foo() has a cyclomatic complexity of 12."}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main/java/Main.java"}, "region": {"startLine": 10}}}]}]}]}'
        )

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="BUILD SUCCESSFUL", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_complexity(target="src/", max_complexity=10)

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 1
        assert result.violations[0].file == "src/main/java/Main.java"
        assert result.violations[0].complexity == 12

    def test_run_debugger_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="DEBUG OK", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target="src/", entrypoint="com.example.Main")

        mock_executor.execute.assert_called_once()
        assert result.exit_code == 0
        assert result.events[0].output == "DEBUG OK"

    def test_run_debugger_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout="DEBUG OK", stderr=""
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_debugger(target="src/", entrypoint="com.example.Main")

        mock_executor.execute.assert_called_once()
        assert result.exit_code == 0
        assert result.events[0].output == "DEBUG OK"

    def test_run_architecture_check_timeout(self, tmp_path: Path) -> None:
        """G-3: run_architecture_check with timed_out=True returns timeout violation."""
        (tmp_path / "pom.xml").write_text("")
        # Write a context.yaml with forbids so the method doesn't short-circuit
        ctx_file = tmp_path / "context.yaml"
        ctx_file.write_text("forbids:\n  - com.evil.*\n")

        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            timed_out=True, duration_seconds=60.0
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_architecture_check(target="src/")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 1
        assert result.violations[0].code == "Timeout"
        assert "timed out" in result.violations[0].message.lower()

    def test_run_architecture_check_violations(self, tmp_path: Path) -> None:
        """G-4: run_architecture_check with ARCH_VIOLATION stdout returns violations."""
        (tmp_path / "pom.xml").write_text("")
        ctx_file = tmp_path / "context.yaml"
        ctx_file.write_text("forbids:\n  - com.evil.*\n")

        arch_stdout = (
            "ARCH_VIOLATION|src/main/java/App.java|com.evil.*\n"
            "ARCH_VIOLATION|src/main/java/Svc.java|com.evil.*\n"
        )
        mock_executor = MagicMock(spec=SubprocessExecutor)
        mock_executor.execute.return_value = _make_result(
            exit_code=0, stdout=arch_stdout
        )
        runner = JavaRunner(cwd=tmp_path, executor=mock_executor)

        result = runner.run_architecture_check(target="src/")

        mock_executor.execute.assert_called_once()
        assert result.violation_count == 2
        assert result.violations[0].file == "src/main/java/App.java"
        assert result.violations[0].code == "C05"
        assert "com.evil.*" in result.violations[0].message
        assert result.violations[1].file == "src/main/java/Svc.java"

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = JavaRunner(cwd=tmp_path)
        assert runner.language_name == "java"

