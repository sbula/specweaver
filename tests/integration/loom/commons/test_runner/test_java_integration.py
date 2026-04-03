import os
from pathlib import Path

import pytest

from specweaver.loom.commons.test_runner.java import JavaRunner

# Since executing Maven and Gradle natively will download dependencies from the internet
# and could take several minutes entirely uncontrolled, we mark these tests as live
# to avoid destroying the normal rapid fast TDD local feedback loop.
pytestmark = pytest.mark.live


@pytest.fixture
def gradle_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "java_gradle_project"


@pytest.fixture
def maven_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "java_maven_project"


def test_java_runner_gradle_integration(gradle_project: Path):
    assert gradle_project.exists(), "Gradle fixture missing"
    
    runner = JavaRunner(cwd=gradle_project)

    # 1. Compile
    res_compile = runner.run_compiler("")
    assert res_compile.error_count == 0, f"Compilation failed: {res_compile.errors}"

    # 2. Test
    res_tests = runner.run_tests("")
    assert res_tests.passed >= 1
    assert res_tests.failed == 0
    assert res_tests.report_path != ""

    # 3. Linter
    res_lint = runner.run_linter("")
    # Our fixture has an intentionally unused private field which PMD flags
    assert res_lint.error_count >= 1
    assert any("unusedField" in e.message or "UnusedPrivateField" in e.code for e in res_lint.errors)

    # 4. Complexity
    res_complex = runner.run_complexity("", max_complexity=10)
    assert res_complex.violation_count >= 1
    complex_issues = [v for v in res_complex.violations if "complexLogic" in v.message or v.complexity > 10]
    assert len(complex_issues) >= 1
    assert complex_issues[0].complexity > 10


def test_java_runner_maven_integration(maven_project: Path):
    assert maven_project.exists(), "Maven fixture missing"
    
    runner = JavaRunner(cwd=maven_project)

    # 1. Compile
    res_compile = runner.run_compiler("")
    assert res_compile.error_count == 0, f"Compilation failed: {res_compile.errors}"

    # 2. Test
    res_tests = runner.run_tests("")
    assert res_tests.passed >= 1
    assert res_tests.failed == 0
    assert res_tests.report_path != ""

    # 3. Linter
    res_lint = runner.run_linter("")
    assert res_lint.error_count >= 1

    # 4. Complexity
    res_complex = runner.run_complexity("", max_complexity=10)
    assert res_complex.violation_count >= 1
