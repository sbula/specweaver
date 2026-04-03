from pathlib import Path

import pytest

from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom
from specweaver.loom.tools.test_runner.tool import TestRunnerTool

pytestmark = pytest.mark.live

@pytest.fixture
def gradle_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent.parent / "fixtures" / "java_gradle_project"

@pytest.fixture
def maven_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent.parent / "fixtures" / "java_maven_project"

def test_java_tool_gradle_integration(gradle_project: Path) -> None:
    assert gradle_project.exists(), "Gradle fixture missing"
    atom = TestRunnerAtom(cwd=gradle_project, language="java")
    tool = TestRunnerTool(atom=atom, role="implementer")

    res_compile = tool.run_compiler(target="src/")
    assert res_compile.status == "success", res_compile.message

    res_tests = tool.run_tests(target="src/")
    assert res_tests.status == "success", res_tests.message
    assert res_tests.data and res_tests.data.get("passed", 0) >= 1

    res_lint = tool.run_linter(target="src/")
    assert res_lint.status == "error", "Expected lint failures"
    assert res_lint.data and res_lint.data.get("error_count", 0) >= 1

    res_complex = tool.run_complexity(target="src/", max_complexity=10)
    assert res_complex.status == "error", "Expected complexity violation"
    assert res_complex.data and res_complex.data.get("violation_count", 0) >= 1

    res_debug = tool.run_debugger(target="src/", entrypoint="com.example.Main")
    assert res_debug.status == "success", res_debug.message

def test_java_tool_maven_integration(maven_project: Path) -> None:
    assert maven_project.exists(), "Maven fixture missing"
    atom = TestRunnerAtom(cwd=maven_project, language="java")
    tool = TestRunnerTool(atom=atom, role="implementer")

    res_compile = tool.run_compiler(target="src/")
    assert res_compile.status == "success", res_compile.message

    res_tests = tool.run_tests(target="src/")
    assert res_tests.status == "success", res_tests.message

    res_lint = tool.run_linter(target="src/")
    assert res_lint.status == "error", "Expected lint failures"

    res_complex = tool.run_complexity(target="src/", max_complexity=10)
    assert res_complex.status == "error", "Expected complexity violation"

    res_debug = tool.run_debugger(target="src/", entrypoint="com.example.Main")
    assert res_debug.status == "success", res_debug.message
