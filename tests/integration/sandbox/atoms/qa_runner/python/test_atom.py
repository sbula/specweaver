from pathlib import Path

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

QARunnerAtom.__test__ = False  # type: ignore[attr-defined]

pytestmark = pytest.mark.live


@pytest.fixture
def python_project() -> Path:
    # Use the specweaver repository itself as a python fixture since it has pytest and ruff configured
    return Path(__file__).parent.parent.parent.parent.parent.parent


def test_python_atom_integration(python_project: Path) -> None:
    assert python_project.exists(), "Python fixture missing"
    atom = QARunnerAtom(cwd=python_project, language="python")

    # 1. Compile
    res_compile = atom.run({"intent": "run_compiler", "target": "tests/"})
    assert res_compile.status == AtomStatus.SUCCESS, res_compile.message

    # 2. Test (use a very restricted target so it doesn't run the entire 12-story battery)
    res_tests = atom.run(
        {"intent": "run_tests", "target": "tests/unit/loom/commons/qa_runner/python/"}
    )
    assert res_tests.status == AtomStatus.SUCCESS, res_tests.message

    # 3. Linter
    res_lint = atom.run(
        {"intent": "run_linter", "target": "tests/unit/loom/commons/qa_runner/python/"}
    )
    assert res_lint.status in [AtomStatus.SUCCESS, AtomStatus.FAILED]

    # 4. Complexity
    res_complex = atom.run(
        {
            "intent": "run_complexity",
            "target": "tests/unit/loom/commons/qa_runner/python/",
            "max_complexity": 10,
        }
    )
    assert res_complex.status in [AtomStatus.SUCCESS, AtomStatus.FAILED]

    # 5. Debugger
    # Let's write a quick temp file to run
    test_py = python_project / ".tmp" / "test_debug.py"
    test_py.parent.mkdir(exist_ok=True)
    test_py.write_text("print('hello debug')")

    res_debug2 = atom.run({"intent": "run_debugger", "target": ".", "entrypoint": str(test_py)})
    assert res_debug2.status == AtomStatus.SUCCESS, res_debug2.message
