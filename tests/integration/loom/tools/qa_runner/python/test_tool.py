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
def python_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent.parent


def test_python_tool_integration(python_project: Path) -> None:
    assert python_project.exists(), "Python fixture missing"
    atom = QARunnerAtom(cwd=python_project, language="python")
    tool = QARunnerTool(atom=atom, role="implementer")

    res_compile = tool.run_compiler(target="tests/")
    assert res_compile.status == "success", res_compile.message

    res_tests = tool.run_tests(target="tests/unit/loom/commons/qa_runner/python/")
    assert res_tests.status == "success", res_tests.message

    res_lint = tool.run_linter(target="tests/unit/loom/commons/qa_runner/python/")
    assert res_lint.status in ["success", "error"]

    res_complex = tool.run_complexity(
        target="tests/unit/loom/commons/qa_runner/python/", max_complexity=10
    )
    assert res_complex.status in ["success", "error"]

    test_py = python_project / ".tmp" / "test_debug.py"
    test_py.parent.mkdir(exist_ok=True)
    test_py.write_text("print('hello debug')")

    res_debug = tool.run_debugger(target=".", entrypoint=str(test_py))
    assert res_debug.status == "success", res_debug.message
