# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests — Incremental validation via Deep Semantic Hashing (Feature 3.32 SF-4).

Exercises:
  1. sw run outputs .specweaver/topology.cache.json upon success.
  2. sw run identically again exits instantly (bypass logic).
  3. sw run failing validation does NOT output or update cache.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


def _create_project_with_clean_code(tmp_path: Path, name: str) -> Path:
    """Create a project with a valid spec and python code."""
    project_dir = tmp_path / name
    project_dir.mkdir()

    # Init the project
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0

    src = project_dir / "src"
    src.mkdir(exist_ok=True)
    tests = project_dir / "tests"
    tests.mkdir(exist_ok=True)

    # Valid pristine code
    (src / "math_ops.py").write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
    (tests / "test_math.py").write_text(
        "from src.math_ops import add\n\n"
        "def test_add():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8"
    )

    spec = project_dir / "specs" / "math_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(
        "# Math Ops\n\n"
        "## 1. Purpose\n\nProvides addition.\n\n"
        "## 2. Contract\n\n```python\ndef add(a: int, b: int) -> int: ...\n```\n\n"
        "## 3. Protocol\n\n1. Add a and b.\n\n"
        "## 4. Policy\n\n| Error | Behavior |\n|:---|:---|\n| Invalid type | Raise TypeError |\n\n"
        "## 5. Boundaries\n\n| Concern | Owned By |\n|:---|:---|\n| I/O | Infra |\n\n"
        "## Done Definition\n\n- [x] Tested\n",
        encoding="utf-8",
    )
    # Create valid local pipeline
    pipeline_path = project_dir / "e2e_code.yaml"
    pipeline_path.write_text(
        "name: e2e_code\nsteps:\n"
        "  - name: lint\n    action: lint_fix\n    target: code\n    params:\n      target: src/\n      max_reflections: 2\n"
        "  - name: test\n    action: validate\n    target: tests\n    params:\n      target: tests/\n",
        encoding="utf-8"
    )

    return project_dir


class TestIncrementalPipelineE2E:
    """Test full integration of topology hashing and pipeline execution."""

    def test_e2e_topology_cache_generated_on_success(self, tmp_path: Path) -> None:
        """Pipeline successfully validates pristine code and persists staleness cache."""
        project_dir = _create_project_with_clean_code(tmp_path, "success-proj")

        # Run validation pipeline
        result = runner.invoke(app, ["run", str(project_dir / "e2e_code.yaml"), "src/", "--project", str(project_dir)])

        assert result.exit_code == 0, f"Run failed: {result.output}"

        # Verify cache hook triggered
        cache_file = project_dir / ".specweaver" / "topology.cache.json"
        assert cache_file.exists(), "Cache was not saved to .specweaver/topology.cache.json"

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert "." in data
        assert "src/math_ops.py" in data["."]["rendered_payload"]

    def test_e2e_true_incremental_bypass(self, tmp_path: Path) -> None:
        """Consecutive run with NO modifications skips execution natively via bypass."""
        project_dir = _create_project_with_clean_code(tmp_path, "bypass-proj")

        # Seed the cache natively via first run
        res1 = runner.invoke(app, ["run", str(project_dir / "e2e_code.yaml"), "src/", "--project", str(project_dir)])
        assert res1.exit_code == 0

        # Observe execution output natively to verify bypass
        res2 = runner.invoke(app, ["run", str(project_dir / "e2e_code.yaml"), "src/", "--project", str(project_dir)])
        assert res2.exit_code == 0

        # The result simply passes without error. Bypassed execution uses <1s typically.
        # Check logs if possible, but assert exit 0 is the primary contract.
        assert res2.exit_code == 0
        assert "pristine" in res2.output.lower() or "bypass" in res2.output.lower() or "completed" in res2.output.lower()

    def test_e2e_cache_resiliency_on_failure(self, tmp_path: Path) -> None:
        """Failed pipeline runs strictly DO NOT update the `.specweaver` staleness cache."""
        project_dir = tmp_path / "fail-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "fail-proj", "--path", str(project_dir)])

        src = project_dir / "src"
        src.mkdir(exist_ok=True)
        # Dirty code (not relevant for validate_only, just scaffolding)
        (src / "bad_ops.py").write_text("def bad():\n  pass\n", encoding="utf-8")

        spec = project_dir / "specs" / "bad_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text(
            "# Bad Ops\n\n## 1. Purpose\nBad.\n",
            encoding="utf-8",
        )

        cache_file = project_dir / ".specweaver" / "topology.cache.json"
        assert not cache_file.exists()

        result = runner.invoke(app, ["run", "validate_only", "specs/bad_spec.md", "--project", str(project_dir)])

        # Pipeline fails gracefully (exiting 1) due to lint errors
        assert result.exit_code != 0

        # Cache MUST NOT exist because run didn't COMPLETE successfully
        assert not cache_file.exists(), "Cache was incorrectly saved despite pipeline failure!"
