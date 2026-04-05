from pathlib import Path

import pytest

from specweaver.loom.atoms.qa_runner.atom import QARunnerAtom as _QARunnerAtom
from specweaver.loom.tools.qa_runner.tool import QARunnerTool as _QARunnerTool

QARunnerAtom = _QARunnerAtom
QARunnerAtom.__test__ = False  # type: ignore
QARunnerTool = _QARunnerTool
QARunnerTool.__test__ = False  # type: ignore

pytestmark = pytest.mark.live


@pytest.fixture
def ts_project_dir(tmp_path: Path) -> Path:
    """Create a minimal TypeScript environment."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "index.ts").write_text("const x: number = 5;\nconsole.log(x);")
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {"strict": true, "noEmit": true}}')
    return tmp_path


def test_typescript_tool_integration(ts_project_dir: Path) -> None:
    atom = QARunnerAtom(cwd=ts_project_dir, language="typescript")
    tool = QARunnerTool(atom=atom, role="implementer")

    res_compile = tool.run_compiler(target="src/")
    assert res_compile.status in ["success", "error"]

    res_tests = tool.run_tests(target=".")
    assert res_tests.status == "success"

    res_debug = tool.run_debugger(target=".", entrypoint="src/index.ts")
    assert res_debug.status in ["success", "error"]
