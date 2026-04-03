from pathlib import Path

import pytest

from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom
from specweaver.loom.tools.test_runner.tool import TestRunnerTool

pytestmark = pytest.mark.live

@pytest.fixture
def rust_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent.parent / "fixtures" / "rust_cargo_project"

def test_rust_tool_integration(rust_project: Path) -> None:
    assert rust_project.exists(), "Rust fixture missing"
    atom = TestRunnerAtom(cwd=rust_project, language="rust")
    tool = TestRunnerTool(atom=atom, role="implementer")

    res_compile = tool.run_compiler(target="src/")
    assert res_compile.status == "success", res_compile.message

    res_tests = tool.run_tests(target="src/")
    assert res_tests.status == "success", res_tests.message

    res_lint = tool.run_linter(target="src/")
    assert res_lint.status in ["success", "error"]

    res_complex = tool.run_complexity(target="src/", max_complexity=10)
    assert res_complex.status in ["success", "error"]

    res_debug = tool.run_debugger(target="src/", entrypoint="src/main.rs")
    assert res_debug.status in ["success", "error"]
