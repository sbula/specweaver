from pathlib import Path

import pytest

from specweaver.core.loom.atoms.base import AtomStatus
from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom

QARunnerAtom.__test__ = False  # type: ignore[attr-defined]

pytestmark = pytest.mark.live


@pytest.fixture
def gradle_project() -> Path:
    return (
        Path(__file__).parent.parent.parent.parent.parent.parent
        / "fixtures"
        / "java_gradle_project"
    )


@pytest.fixture
def maven_project() -> Path:
    return (
        Path(__file__).parent.parent.parent.parent.parent.parent / "fixtures" / "java_maven_project"
    )


def test_java_atom_gradle_integration(gradle_project: Path) -> None:
    assert gradle_project.exists(), "Gradle fixture missing"
    atom = QARunnerAtom(cwd=gradle_project, language="java")

    # 1. Compile
    res_compile = atom.run({"intent": "run_compiler", "target": "src/"})
    assert res_compile.status == AtomStatus.SUCCESS, res_compile.message

    # 2. Test
    res_tests = atom.run({"intent": "run_tests", "target": "src/"})
    assert res_tests.status == AtomStatus.SUCCESS, res_tests.message
    assert res_tests.exports and res_tests.exports.get("passed", 0) >= 1

    # 3. Linter
    res_lint = atom.run({"intent": "run_linter", "target": "src/"})
    assert res_lint.status == AtomStatus.FAILED, "Expected lint failures"
    assert res_lint.exports and res_lint.exports.get("error_count", 0) >= 1

    # 4. Complexity
    res_complex = atom.run({"intent": "run_complexity", "target": "src/", "max_complexity": 10})
    assert res_complex.status == AtomStatus.FAILED, "Expected complexity violation"
    assert res_complex.exports and res_complex.exports.get("violation_count", 0) >= 1

    # 5. Debugger
    res_debug = atom.run(
        {"intent": "run_debugger", "target": "src/", "entrypoint": "com.example.Main"}
    )
    assert res_debug.status == AtomStatus.SUCCESS, res_debug.message


def test_java_atom_maven_integration(maven_project: Path) -> None:
    assert maven_project.exists(), "Maven fixture missing"
    atom = QARunnerAtom(cwd=maven_project, language="java")

    res_compile = atom.run({"intent": "run_compiler", "target": "src/"})
    assert res_compile.status == AtomStatus.SUCCESS, res_compile.message

    res_tests = atom.run({"intent": "run_tests", "target": "src/"})
    assert res_tests.status == AtomStatus.SUCCESS, res_tests.message

    res_lint = atom.run({"intent": "run_linter", "target": "src/"})
    assert res_lint.status == AtomStatus.FAILED, "Expected lint failures"

    res_complex = atom.run({"intent": "run_complexity", "target": "src/", "max_complexity": 10})
    assert res_complex.status == AtomStatus.FAILED, "Expected complexity violation"

    res_debug = atom.run(
        {"intent": "run_debugger", "target": "src/", "entrypoint": "com.example.Main"}
    )
    assert res_debug.status == AtomStatus.SUCCESS, res_debug.message
