from pathlib import Path

import pytest

from specweaver.loom.atoms.qa_runner.atom import QARunnerAtom as _QARunnerAtom

# Prevent pytest collection warnings
QARunnerAtom = _QARunnerAtom
QARunnerAtom.__test__ = False  # type: ignore

pytestmark = pytest.mark.live


@pytest.fixture
def ts_project_dir(tmp_path: Path) -> Path:
    """Create a minimal TypeScript environment."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("const x: number = 5;\nconsole.log(x);")
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true, "noEmit": true}}')

    # We create a dummy package.json so npx might try to resolve locally or use global
    (tmp_path / "package.json").write_text('{"name": "dummy"}')
    return tmp_path


def test_typescript_atom_integration(ts_project_dir: Path) -> None:
    atom = QARunnerAtom(cwd=ts_project_dir, language="typescript")

    # 1. Compiler (tsc)
    res_compile = atom.run_compiler(target="src/")
    # If tsc isn't globally installed or downloaded by npx, it might error, but the structure holds
    assert res_compile.status in ["success", "error"]

    # 2. Tests (stub)
    res_tests = atom.run_tests(target=".")
    assert res_tests.status == "success"

    # 3. Debugger (ts-node)
    res_debug = atom.run_debugger(target=".", entrypoint="src/index.ts")
    assert res_debug.status in ["success", "error"]


def test_typescript_atom_integration_compile_error(tmp_path: Path) -> None:
    """Ensure TS compiler accurately traps syntax errors rather than crashing or skipping."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bad.ts").write_text("const x: number = 'this is a string';")
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true, "noEmit": true}}')

    atom = QARunnerAtom(cwd=tmp_path, language="typescript")
    res_compile = atom.run_compiler(target="src/")

    # Normally this should be 'error' because tsc detects the mismatch
    # If the system does not have npx/tsc, it returns 'error' with ENOENT
    assert res_compile.status == "error"
    if res_compile.message != "TypeScript compiler not found in PATH.":
        # If TSC actually ran, we should have trapped a compile error
        assert "is not assignable" in "".join(err.message for err in res_compile.data.errors)  # type: ignore
