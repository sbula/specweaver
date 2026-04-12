# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for C05 Import Direction Architecture Rule using real Tach."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.core.loom.commons.language.python.runner import PythonQARunner
from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c05_import_direction import ImportDirectionRule

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def tach_workspace(tmp_path: Path) -> Path:
    """Create a temporary workspace with a valid tach.toml and source layout."""
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(tmp_path), check=True)

    src = tmp_path / "src" / "my_project"
    src.mkdir(parents=True)

    (src / "__init__.py").touch()

    core = src / "core"
    core.mkdir()
    (core / "__init__.py").touch()
    core_main = core / "engine.py"
    core_main.write_text("def run(): pass\n")

    ui = src / "ui"
    ui.mkdir()
    (ui / "__init__.py").touch()
    ui_main = ui / "cli.py"
    # This represents a deliberate violation: core importing from ui
    ui_main.write_text("def display(): pass\n")

    bad_core = core / "bad.py"
    bad_core.write_text("from my_project.ui.cli import display\n")

    tach_toml = tmp_path / "tach.toml"
    tach_toml.write_text("""exact = true
source_roots = ["src"]

[[modules]]
path = "<root>"
depends_on = ["my_project.core", "my_project.ui"]

[[modules]]
path = "my_project.core"
depends_on = [] # Core cannot depend on anything

[[modules]]
path = "my_project.ui"
depends_on = ["my_project.core"] # UI CAN depend on Core
""")

    return tmp_path


class TestArchitectureIntegration:
    """Integration stories for Architecture validation."""

    @pytest.mark.integration
    def test_tach_execution_produces_physical_payload(self, tach_workspace: Path) -> None:
        """Story 4: execution of run_architecture_check shells out to tach natively."""
        runner = PythonQARunner(cwd=tach_workspace)
        result = runner.run_architecture_check(target=".")

        # It should run successfully, catching the violation in bad_core
        assert result.violation_count == 1
        assert len(result.violations) == 1

    @pytest.mark.integration
    def test_native_violation_mapping(self, tach_workspace: Path) -> None:
        """Story 5: Execution against real invalid python maps correctly."""
        runner = PythonQARunner(cwd=tach_workspace)
        result = runner.run_architecture_check(target=".")

        print(f"DEBUG: result.violation_count = {result.violation_count}")
        for v in result.violations:
            print(f"DEBUG: violation = {v}")

        v = result.violations[0]
        assert v.code == "UndeclaredDependency", (
            f"Expected UndeclaredDependency, got {v.code}: {v.message}"
        )
        assert "my_project.core" in v.message
        assert "my_project.ui" in v.message

    @pytest.mark.integration
    def test_c05_full_native_invocation(self, tach_workspace: Path) -> None:
        """Story 6: C05 invokes PythonQARunner natively returning RuleResult FAIL."""
        code = (tach_workspace / "src" / "my_project" / "core" / "bad.py").read_text()
        rule = ImportDirectionRule()

        # We pass the file path to run Native architecture check
        result = rule.check(
            code, spec_path=tach_workspace / "src" / "my_project" / "core" / "bad.py"
        )

        assert result.status == Status.FAIL
        assert "architectural violation" in result.message.lower()
        assert len(result.findings) == 1
        assert result.findings[0].severity.value == "error"

    @pytest.mark.integration
    def test_c05_full_native_invocation_pass(self, tach_workspace: Path) -> None:
        """Integration check that fixes rule PASS behavior."""
        # Fix the code
        bad_core = tach_workspace / "src" / "my_project" / "core" / "bad.py"
        bad_core.write_text("def no_imports(): pass\n")

        code = bad_core.read_text()
        rule = ImportDirectionRule()

        result = rule.check(code, spec_path=bad_core)
        assert result.status == Status.PASS
