# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for sw drift commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.cli._core import app

runner = CliRunner()


@pytest.fixture
def dummy_project(tmp_path: Path) -> Path:
    proj = tmp_path / "dummy_proj"
    proj.mkdir()

    plan_path = proj / "plan.yaml"
    plan_path.write_text("""
spec_path: "specs/test_spec.md"
spec_name: "Test"
spec_hash: "123"
timestamp: "2026-01-01T00:00:00Z"
file_layout:
  - path: "src/test.py"
    action: "create"
    purpose: "Test file"
tasks:
  - sequence_number: 1
    name: "Task 1"
    description: "Do it"
    files: ["src/test.py"]
    dependencies: []
    expected_signatures:
      "src/test.py":
        - name: "my_func"
          parameters: ["x", "y"]
          return_type: "int"
    """)

    src_dir = proj / "src"
    src_dir.mkdir()
    src_file = src_dir / "test.py"
    src_file.write_text("def my_func(x, y) -> int:\n    return x + y\n")
    return proj


def test_drift_check_success(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    result = runner.invoke(
        app,
        ["drift", "check", str(target_path), "--plan", str(plan_path), "--project", str(dummy_project)]
    )
    assert result.exit_code == 0
    assert "signatures match specification" in result.stdout


def test_drift_check_failed(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    # Introduce error drift
    target_path.write_text("def bad_func() -> int:\n    return 0\n")

    result = runner.invoke(
        app,
        ["drift", "check", str(target_path), "--plan", str(plan_path), "--project", str(dummy_project)]
    )
    assert result.exit_code == 1
    assert "AST Drift Detected" in result.stdout
    assert "missing_function" not in result.stdout # Should say missing expected method my_func
    assert "my_func" in result.stdout


def test_drift_check_file_not_found(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    result = runner.invoke(
        app,
        ["drift", "check", "nonexistent.py", "--plan", str(plan_path), "--project", str(dummy_project)]
    )
    assert result.exit_code == 1
    assert "File not found" in result.stdout


def test_drift_check_warning(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    # Introduce warning drift (wrong parameter name)
    target_path.write_text("def my_func(a, b) -> int:\n    return a + b\n")

    result = runner.invoke(
        app,
        ["drift", "check", str(target_path), "--plan", str(plan_path), "--project", str(dummy_project)]
    )
    # WARNING shouldn't crash with 1
    assert result.exit_code == 0
    assert "Warnings for test.py" in result.stdout
    assert "warning" in result.stdout


def test_drift_check_invalid_project(dummy_project: Path) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"

    result = runner.invoke(
        app,
        ["drift", "check", str(target_path), "--plan", str(plan_path), "--project", "random/missing/dir"]
    )
    assert result.exit_code == 1
    assert "Error:" in result.stdout


def test_drift_check_analyze(dummy_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    plan_path = dummy_project / "plan.yaml"
    target_path = dummy_project / "src" / "test.py"
    target_path.write_text("def missing() -> int: return 0\n")

    from specweaver.cli import _helpers
    class MockAdapter:
        async def generate(self, *args: list[str], **kwargs: dict[str, str]) -> object:
            class MockResp:
                text = "Mock LLM Root Cause"
            return MockResp()

    monkeypatch.setattr(_helpers, "_require_llm_adapter", lambda p: (None, MockAdapter(), None))

    result = runner.invoke(
        app,
        ["drift", "check", str(target_path), "--plan", str(plan_path), "--project", str(dummy_project), "--analyze"]
    )
    assert result.exit_code == 1
    assert "LLM Root-Cause Analysis" in result.stdout
    assert "Mock LLM Root Cause" in result.stdout
