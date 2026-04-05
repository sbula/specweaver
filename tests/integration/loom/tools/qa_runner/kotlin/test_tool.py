from pathlib import Path

import pytest

from specweaver.loom.atoms.qa_runner.atom import QARunnerAtom as _QARunnerAtom
from specweaver.loom.tools.qa_runner.tool import QARunnerTool as _QARunnerTool

QARunnerAtom = _QARunnerAtom
QARunnerAtom.__test__ = False  # type: ignore[attr-defined]
QARunnerTool = _QARunnerTool
QARunnerTool.__test__ = False  # type: ignore[attr-defined]

pytestmark = pytest.mark.live


@pytest.fixture
def gradle_project() -> Path:
    return (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "fixtures"
        / "kotlin_gradle_project"
    )


@pytest.fixture
def maven_project() -> Path:
    return (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "fixtures"
        / "kotlin_maven_project"
    )


def test_kotlin_tool_gradle_integration(gradle_project: Path) -> None:
    assert gradle_project.exists(), "Gradle fixture missing"
    atom = QARunnerAtom(cwd=gradle_project, language="kotlin")
    tool = QARunnerTool(atom=atom, role="implementer")

    res_compile = tool.run_compiler(target="src/")
    assert res_compile.status == "success", res_compile.message

    res_tests = tool.run_tests(target="src/")
    assert res_tests.status == "success", res_tests.message
    assert res_tests.data and res_tests.data.get("passed", 0) >= 1

    res_lint = tool.run_linter(target="src/")
    assert res_lint.status in ["success", "error"]
    assert res_lint.data and res_lint.data.get("error_count", -1) >= 0

    res_complex = tool.run_complexity(target="src/", max_complexity=10)
    assert res_complex.status == "error", "Expected complexity violation"
    assert res_complex.data and res_complex.data.get("violation_count", 0) >= 1

    res_debug = tool.run_debugger(target="src/", entrypoint="AppKt")
    assert res_debug.status == "success", res_debug.message


def test_kotlin_tool_maven_integration(maven_project: Path) -> None:
    assert maven_project.exists(), "Maven fixture missing"
    atom = QARunnerAtom(cwd=maven_project, language="kotlin")
    tool = QARunnerTool(atom=atom, role="implementer")

    res_compile = tool.run_compiler(target="src/")
    assert res_compile.status == "success", res_compile.message

    res_tests = tool.run_tests(target="src/")
    assert res_tests.status == "success", res_tests.message

    res_lint = tool.run_linter(target="src/")
    assert res_lint.status in ["error", "success"]

    res_complex = tool.run_complexity(target="src/", max_complexity=10)
    assert res_complex.status == "error", "Expected complexity violation"

    res_debug = tool.run_debugger(target="src/", entrypoint="AppKt")
    assert res_debug.status == "success", res_debug.message
