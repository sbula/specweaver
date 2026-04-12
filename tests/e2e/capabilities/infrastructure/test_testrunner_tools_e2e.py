# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests for QARunnerTool integration."""

import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

runner = CliRunner()


def test_e2e_python_qarunner_tooling(tmp_path: Path) -> None:
    """E2E boundary test validating python compiler and debugger via CLI invocation."""
    project_dir = tmp_path / "py_proj"
    project_dir.mkdir()
    runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

    # Setup some python code
    target_dir = project_dir / "src" / "debug"
    target_dir.mkdir(parents=True, exist_ok=True)
    py_file = target_dir / "app.py"
    py_file.write_text('print("E2E_PYTHON_STDOUT")', encoding="utf-8")

    from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom
    from specweaver.core.loom.tools.qa_runner.tool import QARunnerTool

    atom = QARunnerAtom(cwd=project_dir)
    tool = QARunnerTool(atom=atom, role="implementer")

    # E2E proxy of run_compiler
    compile_result = tool.run_compiler(target=str(target_dir))
    assert hasattr(compile_result, "data")
    assert compile_result.data["error_count"] == 0

    # E2E proxy of run_debugger
    debug_result = tool.run_debugger(target=str(target_dir), entrypoint=str(py_file))
    assert hasattr(debug_result, "data")
    assert debug_result.data["exit_code"] == 0
    assert "E2E_PYTHON_STDOUT" in str(debug_result.data["events"])


def test_e2e_typescript_qarunner_tooling(tmp_path: Path) -> None:
    """E2E boundary test validating TS compiler and debugger via CLI invocation."""
    project_dir = tmp_path / "ts_proj"
    project_dir.mkdir()
    runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

    # Configure project for TS logic
    (project_dir / "package.json").write_text('{"name": "ts_proj"}', encoding="utf-8")

    # Generate local tsconfig to compile correctly.
    (project_dir / "tsconfig.json").write_text(
        '{"compilerOptions": {"noEmit": true}, "include": ["src/**/*"]}', encoding="utf-8"
    )

    npm_bin = shutil.which("npm") or "npm"
    subprocess.run(
        [npm_bin, "install", "typescript", "ts-node", "@types/node"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    target_dir = project_dir / "src" / "ts_debug"
    target_dir.mkdir(parents=True, exist_ok=True)
    ts_file_compile = target_dir / "bad.ts"
    ts_file_compile.write_text('let a: number = "bad";', encoding="utf-8")

    ts_file_debug = target_dir / "app.ts"
    ts_file_debug.write_text('console.log("E2E_TS_STDOUT");', encoding="utf-8")

    from specweaver.core.loom.atoms.qa_runner.atom import QARunnerAtom
    from specweaver.core.loom.tools.qa_runner.tool import QARunnerTool

    atom = QARunnerAtom(cwd=project_dir, language="typescript")
    tool = QARunnerTool(atom=atom, role="implementer")

    # E2E proxy of run_compiler
    compile_result = tool.run_compiler(target=".")
    assert compile_result.data["error_count"] > 0

    # E2E proxy of run_debugger
    debug_result = tool.run_debugger(target=str(target_dir), entrypoint=str(ts_file_debug))
    assert "E2E_TS_STDOUT" in str(debug_result.data["events"])
