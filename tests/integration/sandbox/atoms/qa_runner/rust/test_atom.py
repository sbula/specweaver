from pathlib import Path

import pytest

from specweaver.sandbox.base import AtomStatus
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

QARunnerAtom.__test__ = False  # type: ignore[attr-defined]

pytestmark = pytest.mark.live


@pytest.fixture
def rust_project() -> Path:
    return (
        Path(__file__).parent.parent.parent.parent.parent.parent / "fixtures" / "rust_cargo_project"
    )


def test_rust_atom_integration(rust_project: Path) -> None:
    assert rust_project.exists(), "Rust fixture missing"
    atom = QARunnerAtom(cwd=rust_project, language="rust")

    res_compile = atom.run({"intent": "run_compiler", "target": "src/"})
    assert res_compile.status == AtomStatus.SUCCESS, res_compile.message

    res_tests = atom.run({"intent": "run_tests", "target": "src/"})
    assert res_tests.status == AtomStatus.SUCCESS, res_tests.message

    res_lint = atom.run({"intent": "run_linter", "target": "src/"})
    assert res_lint.status in [AtomStatus.SUCCESS, AtomStatus.FAILED]

    res_complex = atom.run({"intent": "run_complexity", "target": "src/", "max_complexity": 10})
    assert res_complex.status in [AtomStatus.SUCCESS, AtomStatus.FAILED]

    res_debug = atom.run({"intent": "run_debugger", "target": "src/", "entrypoint": "src/main.rs"})
    assert res_debug.status in [AtomStatus.SUCCESS, AtomStatus.FAILED]
