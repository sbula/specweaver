# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for JavaRunner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.core.loom.commons.language.java.runner import JavaRunner


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
        runner = JavaRunner(cwd=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="BUILD SUCCESSFUL", stderr="")
            result = runner.run_compiler(target="src/")

            mock_run.assert_called_once()
            assert (
                "gradlew" in mock_run.call_args[0][0][0] or "gradle" in mock_run.call_args[0][0][0]
            )
            assert "compileJava" in mock_run.call_args[0][0]
            assert result.error_count == 0

    def test_run_compiler_maven_success(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        runner = JavaRunner(cwd=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
            result = runner.run_compiler(target="src/")

            mock_run.assert_called_once()
            assert "mvnw" in mock_run.call_args[0][0][0] or "mvn" in mock_run.call_args[0][0][0]
            assert "compile" in mock_run.call_args[0][0]
            assert result.error_count == 0

    def test_run_tests_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")

        # Create a stale XML to verify it's cleared
        stale_xml = tmp_path / "build" / "test-results" / "test" / "TEST-stale.xml"
        stale_xml.parent.mkdir(parents=True, exist_ok=True)
        stale_xml.write_text("<testsuite><testcase name='failure'/></testsuite>")

        runner = JavaRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="BUILD SUCCESSFUL", stderr="")

            # Since we mock subprocess, it won't actually generate new XMLs,
            # but we can verify that the old XML is DELETED.
            with patch("junitparser.JUnitXml.fromfile") as mock_fromfile:
                # Mock returning no tests for the parsed files
                mock_fromfile.return_value = []
                result = runner.run_tests(target="src/")

                assert not stale_xml.exists(), "Stale XML was not cleared before running tests!"

                mock_run.assert_called_once()
                assert "test" in mock_run.call_args[0][0]
                assert result.passed == 0
                assert result.failed == 0

    def test_run_tests_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")

        stale_xml = tmp_path / "target" / "surefire-reports" / "TEST-stale.xml"
        stale_xml.parent.mkdir(parents=True, exist_ok=True)
        stale_xml.write_text("<testsuite><testcase name='failure'/></testsuite>")

        runner = JavaRunner(cwd=tmp_path)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
            with patch("junitparser.JUnitXml.fromfile") as mock_fromfile:
                mock_fromfile.return_value = []
                result = runner.run_tests(target="src/")

                assert not stale_xml.exists(), "Stale XML was not cleared before running tests!"

                mock_run.assert_called_once()
                assert "test" in mock_run.call_args[0][0]
                assert result.passed == 0
                assert result.failed == 0

    def test_run_linter_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        runner = JavaRunner(cwd=tmp_path)

        pmd_file = tmp_path / "build" / "reports" / "pmd" / "main.sarif"
        pmd_file.parent.mkdir(parents=True, exist_ok=True)
        pmd_file.write_text(
            '{"runs": [{"results": [{"message": {"text": "A lint error"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main/java/Main.java"}, "region": {"startLine": 10}}}]}]}]}'
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="BUILD SUCCESSFUL", stderr="")
            result = runner.run_linter(target="src/")

            mock_run.assert_called_once()
            assert "pmdMain" in mock_run.call_args[0][0]
            assert result.error_count == 1
            assert result.errors[0].message == "A lint error"
            assert result.errors[0].file == "src/main/java/Main.java"
            assert result.errors[0].line == 10

    def test_run_linter_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        runner = JavaRunner(cwd=tmp_path)

        pmd_file = tmp_path / "target" / "pmd.sarif"
        pmd_file.parent.mkdir(parents=True, exist_ok=True)
        pmd_file.write_text(
            '{"runs": [{"results": [{"message": {"text": "A lint error"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main/java/Main.java"}, "region": {"startLine": 10}}}]}]}]}'
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
            result = runner.run_linter(target="src/")

            mock_run.assert_called_once()
            assert "pmd:pmd" in mock_run.call_args[0][0]
            assert result.error_count == 1
            assert result.errors[0].message == "A lint error"

    def test_run_complexity_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        runner = JavaRunner(cwd=tmp_path)

        pmd_file = tmp_path / "build" / "reports" / "pmd" / "main.sarif"
        pmd_file.parent.mkdir(parents=True, exist_ok=True)
        pmd_file.write_text(
            '{"runs": [{"results": [{"ruleId": "CyclomaticComplexity", "properties": {"complexity": 12}, "message": {"text": "The method foo() has a cyclomatic complexity of 12."}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main/java/Main.java"}, "region": {"startLine": 10}}}]}]}]}'
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="BUILD SUCCESSFUL", stderr="")
            result = runner.run_complexity(target="src/", max_complexity=10)

            mock_run.assert_called_once()
            assert "pmdMain" in mock_run.call_args[0][0]
            assert result.violation_count == 1
            assert result.violations[0].file == "src/main/java/Main.java"
            assert result.violations[0].complexity == 12

    def test_run_debugger_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("")
        runner = JavaRunner(cwd=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="DEBUG OK", stderr="")
            result = runner.run_debugger(target="src/", entrypoint="com.example.Main")

            mock_run.assert_called_once()
            assert "build" in mock_run.call_args[0][0]
            assert result.exit_code == 0
            assert result.events[0].output == "DEBUG OK"

    def test_run_debugger_maven(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("")
        runner = JavaRunner(cwd=tmp_path)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="DEBUG OK", stderr="")
            result = runner.run_debugger(target="src/", entrypoint="com.example.Main")

            mock_run.assert_called_once()
            assert "compile" in mock_run.call_args[0][0]
            assert result.exit_code == 0
            assert result.events[0].output == "DEBUG OK"

    def test_language_name_property(self, tmp_path: Path) -> None:
        runner = JavaRunner(cwd=tmp_path)
        assert runner.language_name == "java"
