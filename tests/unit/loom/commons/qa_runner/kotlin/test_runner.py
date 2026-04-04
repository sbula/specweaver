import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.loom.commons.qa_runner.kotlin.runner import KotlinRunner


class TestKotlinRunner:
    @pytest.fixture
    def mock_cwd(self, tmp_path: Path) -> Path:
        return tmp_path

    @pytest.fixture
    def kotlin_runner(self, mock_cwd: Path) -> KotlinRunner:
        return KotlinRunner(cwd=mock_cwd)

    @patch("subprocess.run")
    def test_run_compiler_gradle(self, mock_run: MagicMock, mock_cwd: Path, kotlin_runner: KotlinRunner) -> None:
        # Create a build.gradle to anchor gradle logic
        (mock_cwd / "build.gradle").touch()

        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "BUILD SUCCESSFUL"

        res = kotlin_runner.run_compiler(target="")
        assert res.error_count == 0
        assert mock_run.call_args[0][0][1] == "compileKotlin"

    @patch("subprocess.run")
    def test_run_tests_wipes_stale_xml(self, mock_run: MagicMock, mock_cwd: Path, kotlin_runner: KotlinRunner) -> None:
        # Create a build.gradle
        (mock_cwd / "build.gradle").touch()
        build_dir = mock_cwd / "build" / "test-results"
        build_dir.mkdir(parents=True)
        stale_xml = build_dir / "TEST-stale.xml"
        stale_xml.touch()

        # Mocking run so we just verify deletion
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "BUILD SUCCESSFUL"

        res = kotlin_runner.run_tests(target="")
        # Should have verified it unlinks XMLs before testing
        assert not stale_xml.exists()
        assert res.total >= 0

    @patch("subprocess.run")
    def test_run_linter_detekt_sarif(self, mock_run: MagicMock, mock_cwd: Path, kotlin_runner: KotlinRunner) -> None:
        (mock_cwd / "build.gradle").touch()

        # Write mock Detekt SARIF json
        report_dir = mock_cwd / "build" / "reports" / "detekt"
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
                                        "region": {"startLine": 10, "startColumn": 5}
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        sarif_file.write_text(json.dumps(mock_sarif), "utf-8")

        res = kotlin_runner.run_linter(target="")
        assert res.error_count == 1
        assert res.errors[0].message == "This block is empty."
        assert res.errors[0].line == 10
        assert res.errors[0].file == "src/main/kotlin/App.kt"

    @patch("subprocess.run")
    def test_run_complexity_detekt_sarif(self, mock_run: MagicMock, mock_cwd: Path, kotlin_runner: KotlinRunner) -> None:
        (mock_cwd / "build.gradle").touch()

        # Write mock Detekt SARIF json targeting a complexity rule
        report_dir = mock_cwd / "build" / "reports" / "detekt"
        report_dir.mkdir(parents=True, exist_ok=True)
        sarif_file = report_dir / "detekt.sarif"

        mock_sarif = {
            "runs": [
                {
                    "results": [
                        {
                            "ruleId": "ComplexMethod",
                            "properties": {"complexity": 15},
                            "message": {"text": "The function complexLogic appears to be too complex (15)."},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "App.kt"},
                                        "region": {"startLine": 20}
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        sarif_file.write_text(json.dumps(mock_sarif), "utf-8")

        res = kotlin_runner.run_complexity(target="")
        # complexLogic overrides max_complexity (10 by default) as parsed from SARIF 15
        assert res.violation_count == 1
        assert res.violations[0].complexity == 15
        assert res.violations[0].line == 20

    @patch("subprocess.run")
    def test_run_debugger(self, mock_run: MagicMock, mock_cwd: Path, kotlin_runner: KotlinRunner) -> None:
        (mock_cwd / "build.gradle").touch()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Listening for transport dt_socket at address: 5005\nTest JVM Output"

        res = kotlin_runner.run_debugger(target="", entrypoint="AppKt")
        assert len(res.events) > 0
        assert "5005" in res.events[-1].output or "AppKt" in res.events[0].output
