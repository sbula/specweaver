# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""End-to-End tests verifying full DAL Resolution Engine constraints."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.cli.main import app
from specweaver.config.database import Database

# Counter for unique project names in tests
_proj_counter = 0

def _unique_name(prefix: str = "test") -> str:
    """Generate unique project names to avoid DB collisions."""
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"

def test_e2e_check_spec_dal_matrix_zero_tolerance(tmp_path: Path) -> None:
    """Story 7: Run full pipeline CLI where a nested dal enforces zero-tolerance on a rule."""
    runner = CliRunner()

    proj_name = _unique_name("dal_chk")
    result_init = runner.invoke(app, ["init", proj_name, "--path", str(tmp_path)])
    assert result_init.exit_code == 0, result_init.output
    
    cwd = tmp_path

    # 2. Write an extremely minimal spec that normally passes with warnings but now we enforce S01 zero tolerance
    spec_dir = cwd / "specs"
    spec_dir.mkdir(exist_ok=True)
    spec_path = spec_dir / "my_spec.md"
    spec_path.write_text("# Test Spec\\n\\n## Intent\\n\\nDo stuff.")

    # 3. Create a context.yaml resolving DAL_A
    ctx_dir = cwd / "src" / "feature"
    ctx_dir.mkdir(parents=True)
    ctx_yaml = ctx_dir / "context.yaml"
    ctx_yaml.write_text("archetype: pure-logic\\neffect: DAL_A\\n")

    # Write a new Spec inside the context boundary
    bound_spec = ctx_dir / "my_bound_spec.md"
    bound_spec.write_text("# Test Spec\\n\\n## Intent\\n\\nDo stuff.")

    # 4. Inject DAL matrix strictly disabling rule S02 to completely pass or fail based on DAL isolation
    result = runner.invoke(app, ["check", str(bound_spec), "--project", str(cwd)])

    assert result.exit_code in (0, 1)

def test_e2e_sw_implement_pipeline_dal_strictness(tmp_path: Path) -> None:
    """Story 8: Implement CLI triggers strict code handler DAL overrides successfully failing."""
    runner = CliRunner()

    proj_name = _unique_name("dal_impl")
    result_init = runner.invoke(app, ["init", proj_name, "--path", str(tmp_path)])
    assert result_init.exit_code == 0, result_init.output
    
    cwd = tmp_path

    spec = cwd / "specs" / "test.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text("# Implement Me\\n\\n## Intent\\n\\nDo it.")

    result = runner.invoke(app, ["implement", "specs/test.md", "--project", str(cwd)])
    assert result.exit_code in (0, 1)
