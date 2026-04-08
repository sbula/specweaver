# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for the Git Pre-Commit Hook (Feature 3.23 SF-2)."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from specweaver.cli.main import app

runner = CliRunner()


def test_rot_check_exits_42_on_drift(tmp_path: Path) -> None:
    """Test that sw drift check-rot --staged dynamically checks files and exits 42 on drift."""
    # 1. Setup a dummy workspace
    proj_dir = tmp_path / "rot_proj"
    proj_dir.mkdir()

    # 2. Setup the specs directory and plan
    specs_dir = proj_dir / "specs"
    specs_dir.mkdir()
    plan_path = specs_dir / "test_plan.yaml"
    plan_path.write_text("""
spec_path: "specs/feature.md"
spec_name: "Mock Spec"
spec_hash: "mock"
file_layout:
  - path: "src/drifted.py"
    action: "create"
    purpose: "mock"
timestamp: "2026-04-01T00:00:00Z"
tasks:
  - sequence_number: 1
    name: "task"
    description: "task"
    files: ["src/drifted.py"]
    expected_signatures:
      "src/drifted.py":
        - name: "hello"
          parameters: ["param1"]
          return_type: "str"
""")

    # 3. Setup drifted Python file
    src_dir = proj_dir / "src"
    src_dir.mkdir()
    code_file = src_dir / "drifted.py"
    # Change method name to trigger Missing Method ERROR and Unauthorized Method ERROR
    code_file.write_text("def different_func() -> str:\n    return 'diff\n'")

    class MockGitResult:
        stdout = str(code_file) + "\n"

    # 4. Mock subprocess to simulate `git diff --cached --name-only`
    with (
        patch("specweaver.cli.drift.subprocess.run") as mock_run,
        patch("specweaver.cli.drift.resolve_project_path") as mock_resolve,
    ):
        mock_run.return_value = MockGitResult()
        mock_resolve.return_value = proj_dir

        result = runner.invoke(app, ["drift", "check-rot", "--staged"])

    # 5. Assert 42 Exit Code and proper output for Structural Drift
    if result.exit_code != 42:
        print("FAIL OUTPUT:", result.output)
        if result.exception:
            import traceback

            traceback.print_exception(
                type(result.exception), result.exception, result.exception.__traceback__
            )
    assert result.exit_code == 42
    assert "AST Drift Detected" in result.output
    assert "src/drifted.py" in result.output


def test_rot_check_exits_0_on_clean(tmp_path: Path) -> None:
    """Test that cleanly mapped ASTs do not trigger the 42 Git Hook."""
    proj_dir = tmp_path / "clean_proj"
    proj_dir.mkdir()

    specs_dir = proj_dir / "specs"
    specs_dir.mkdir()
    (specs_dir / "clean_plan.yaml").write_text("""
spec_path: "specs/feature2.md"
spec_name: "Mock Spec"
spec_hash: "mock"
file_layout:
  - path: "src/clean.py"
    action: "create"
    purpose: "mock"
timestamp: "2026-04-01T00:00:00Z"
tasks:
  - sequence_number: 1
    name: "task"
    description: "task"
    files: ["src/clean.py"]
    expected_signatures:
      "src/clean.py":
        - name: "hello"
          parameters: ["param1"]
          return_type: "str"
""")

    src_dir = proj_dir / "src"
    src_dir.mkdir()
    code_file = src_dir / "clean.py"
    code_file.write_text("def hello(param1: str) -> str:\n    return param1\n")

    class MockGitResult:
        stdout = str(code_file) + "\n"

    with (
        patch("specweaver.cli.drift.subprocess.run") as mock_run,
        patch("specweaver.cli.drift.resolve_project_path") as mock_resolve,
    ):
        mock_run.return_value = MockGitResult()
        mock_resolve.return_value = proj_dir

        result = runner.invoke(app, ["drift", "check-rot", "--staged"])

    if result.exit_code != 0:
        Path(".tmp/test_output.log").write_text(result.output, encoding="utf-8")
        print("FAIL OUTPUT CLEAN:", result.output)
        if result.exception:
            import traceback

            traceback.print_exception(
                type(result.exception), result.exception, result.exception.__traceback__
            )

    assert result.exit_code == 0
    assert "AST signatures match" in result.output


def test_rot_check_polyglot_ts(tmp_path: Path) -> None:
    """Test that staged non-Python files bypass TreeSitter and return 0 (success) natively."""
    proj_dir = tmp_path / "ts_proj"
    proj_dir.mkdir()

    (proj_dir / "specs").mkdir()
    (proj_dir / "specs" / "test_plan.yaml").write_text(
        "spec_path: f\nspec_name: name\nspec_hash: h\ntimestamp: '2026-04-01'\nfile_layout: []\ntasks: []"
    )

    src_dir = proj_dir / "src"
    src_dir.mkdir()
    code_file = src_dir / "index.ts"
    code_file.write_text("console.log('hello');")

    class MockGitResult:
        stdout = str(code_file) + "\n"

    with (
        patch("specweaver.cli.drift.subprocess.run") as mock_run,
        patch("specweaver.cli.drift.resolve_project_path") as mock_resolve,
    ):
        mock_run.return_value = MockGitResult()
        mock_resolve.return_value = proj_dir
        result = runner.invoke(app, ["drift", "check-rot", "--staged"])

    assert result.exit_code == 0


def test_rot_check_windows_newlines(tmp_path: Path) -> None:
    """Test handling of Git diff output containing \\r\\n in paths."""
    proj_dir = tmp_path / "win_proj"
    proj_dir.mkdir()

    (proj_dir / "specs").mkdir()
    (proj_dir / "specs" / "test_plan.yaml").write_text(
        "spec_path: f\nspec_name: name\nspec_hash: h\ntimestamp: '2026-04-01'\nfile_layout: []\ntasks: []"
    )

    src_dir = proj_dir / "src"
    src_dir.mkdir()
    code_file = src_dir / "clean.py"
    code_file.write_text("def hello() -> str:\n    return 'hello'\n")

    class MockGitResult:
        stdout = f'"{code_file!s}"\r\n'

    with (
        patch("specweaver.cli.drift.subprocess.run") as mock_run,
        patch("specweaver.cli.drift.resolve_project_path") as mock_resolve,
    ):
        mock_run.return_value = MockGitResult()
        mock_resolve.return_value = proj_dir
        result = runner.invoke(app, ["drift", "check-rot", "--staged"])

    assert result.exit_code == 0
