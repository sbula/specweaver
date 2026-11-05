# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Rule C05: a tach boundary violation reaching a spec review as a finding.

Proves: C-EXEC-01 FR-4

Cited under `specweaver-dev` §3.2c, from `INT-US-01-SF02-MIG`. Mutant: the `violation_count == 0`
branch forced true, so the rule always passes — 4 fail across three tiers.

FR-4 is the half of this capability that is *product*, not repo hygiene: `tach check` runs against an
analysed project and each violation becomes an ERROR `Finding` with a message a reviewer can act on. An
exit code is not a review.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.orchestration.validation_hydrator import _hydrate_architecture
from specweaver.assurance.validation.rules.code.c05_import_direction import ImportDirectionRule
from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.language.core.boundary_check import check_architecture
from specweaver.sandbox.language.core.runner_factory import qa_atom

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

    # The shared boundary check judges files a manifest covers; this one allows the whole package,
    # so every finding below is tach's (TECH-082: tach runs as the configured extra).
    (src / "context.yaml").write_text("name: my_project\narchetype: orchestrator\n")

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


_BAD = "src/my_project/core/bad.py"


def _run_architecture_and_build_context(workspace: Path) -> dict:
    """C05's context as the real hydrator builds it, from the real QA atom."""
    atom = qa_atom(cwd=workspace, language="python")
    return {
        "qa_architecture_result": _hydrate_architecture(atom, workspace / _BAD, workspace, None)
    }


class TestArchitectureIntegration:
    """Integration stories for Architecture validation."""

    @pytest.mark.integration
    def test_tach_execution_produces_physical_payload(self, tach_workspace: Path) -> None:
        """Story 4: the architecture check shells out to tach natively."""
        result = check_architecture(tach_workspace, _BAD, SubprocessExecutor(cwd=tach_workspace))

        # It should run successfully, catching the violation in bad_core
        assert result.violation_count == 1
        assert len(result.violations) == 1

    @pytest.mark.integration
    def test_native_violation_mapping(self, tach_workspace: Path) -> None:
        """Story 5: Execution against real invalid python maps correctly."""
        result = check_architecture(tach_workspace, _BAD, SubprocessExecutor(cwd=tach_workspace))

        v = result.violations[0]
        assert v.code == "tach:UndeclaredDependency", (
            f"Expected tach:UndeclaredDependency, got {v.code}: {v.message}"
        )
        assert "my_project.core" in v.message
        assert "my_project.ui" in v.message

    @pytest.mark.integration
    def test_c05_full_native_invocation(self, tach_workspace: Path) -> None:
        """Story 6: C05 reads hydrated QA context from real tach run → FAIL."""
        code = (tach_workspace / "src" / "my_project" / "core" / "bad.py").read_text()
        rule = ImportDirectionRule()
        # Inject pre-hydrated context from native tach execution
        rule.context = _run_architecture_and_build_context(tach_workspace)

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
        # Inject pre-hydrated context from native tach execution (no violations now)
        rule.context = _run_architecture_and_build_context(tach_workspace)

        result = rule.check(code, spec_path=bad_core)
        assert result.status == Status.PASS
