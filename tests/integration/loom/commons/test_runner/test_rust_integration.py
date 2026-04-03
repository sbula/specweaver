from pathlib import Path

import pytest

from specweaver.loom.commons.test_runner.rust import RustRunner

pytestmark = pytest.mark.live


@pytest.fixture
def rust_project() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent / "fixtures" / "rust_cargo_project"


def test_rust_runner_integration(rust_project: Path):
    assert rust_project.exists(), "Rust fixture missing"

    runner = RustRunner(cwd=rust_project)

    # 1. Compile
    res_compile = runner.run_compiler("")
    assert res_compile.error_count == 0, f"Compilation failed: {res_compile.errors}"

    # 2. Test
    res_tests = runner.run_tests("")
    assert res_tests.total >= 0

    # 3. Linter
    res_lint = runner.run_linter("")
    assert res_lint.error_count >= 0

    # 4. Complexity
    res_complex = runner.run_complexity("", max_complexity=10)
    assert res_complex.violation_count >= 0
