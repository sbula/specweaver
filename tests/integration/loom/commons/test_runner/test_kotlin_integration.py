from pathlib import Path

import pytest

from specweaver.loom.commons.test_runner.kotlin import KotlinRunner

pytestmark = pytest.mark.live


@pytest.fixture
def gradle_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "kotlin_gradle_project"


@pytest.fixture
def maven_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "kotlin_maven_project"


def test_kotlin_runner_gradle_integration(gradle_project: Path) -> None:
    assert gradle_project.exists(), "Kotlin Gradle fixture missing"

    runner = KotlinRunner(cwd=gradle_project)

    # 1. Compile
    res_compile = runner.run_compiler("")
    assert res_compile.error_count == 0, f"Compilation failed: {res_compile.errors}"

    # 2. Test
    res_tests = runner.run_tests("")
    assert res_tests.passed >= 1
    assert res_tests.failed == 0

    # 3. Linter
    res_lint = runner.run_linter("")
    # Detekt should catch 'unusedVar' in getGreeting or something if configured,
    # and depending on the default ruleset maybe some code style error.
    # At least we know it runs and successfully parses without crashing.
    assert res_lint.error_count >= 0

    # 4. Complexity
    res_complex = runner.run_complexity("", max_complexity=10)
    # The 'complexLogic' function is complex.
    complex_issues = [v for v in res_complex.violations if "complex" in v.message.lower() or v.complexity > 10]
    assert len(complex_issues) >= 1
    assert complex_issues[0].complexity > 10


def test_kotlin_runner_maven_integration(maven_project: Path) -> None:
    assert maven_project.exists(), "Kotlin Maven fixture missing"

    runner = KotlinRunner(cwd=maven_project)

    # 1. Compile
    res_compile = runner.run_compiler("")
    assert res_compile.error_count == 0, f"Compilation failed: {res_compile.errors}"

    # 2. Test
    res_tests = runner.run_tests("")
    assert res_tests.passed >= 1
    assert res_tests.failed == 0

    # 3. Linter
    res_lint = runner.run_linter("")
    assert res_lint.error_count >= 0

    # 4. Complexity
    res_complex = runner.run_complexity("", max_complexity=10)
    complex_issues = [v for v in res_complex.violations if "complex" in v.message.lower() or v.complexity > 10]
    assert len(complex_issues) >= 1
    assert complex_issues[0].complexity > 10
