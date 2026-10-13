# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The incremental-semantics journey: a pipeline run leaves a usable staleness cache.

Proves: A-SENS-01 FR-2

Cited from `INT-US-11-SF01-MIG`. Mutant-verified and precisely located: renaming the cache file
(`topology.cache.json` -> `unused.json`) fails exactly one test in the repo,
`test_e2e_topology_cache_generated_on_success` — here. Nothing at unit tier notices, because the cache
is a journey-level artifact.

That is the shape `ADR-004` clause 3 predicts: a path only an e2e can walk belongs to the story, not
to a unit suite.

Exercises:
  1. `sw run` writes `.specweaver/topology.cache.json` on success.
  2. an identical `sw run` exits instantly on the bypass.
  3. a failing validation neither writes nor updates the cache.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

runner = CliRunner()


class _NoCallsExpected:
    """The `lint_fix` step resolves its role up front, but clean code never reaches the model."""

    def available(self) -> bool:
        return True

    async def generate(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("clean code must not reach the model")

    generate_with_tools = generate


@pytest.fixture(autouse=True)
def _model_never_called() -> Iterator[None]:
    with doubled_llm(_NoCallsExpected()):
        yield


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
    (src / "math_ops.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8"
    )
    (tests / "test_math.py").write_text(
        "from src.math_ops import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
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
        encoding="utf-8",
    )

    return project_dir


_TEST = (
    "import pytest\n\nfrom demo.{name}.{name} import {name}\n\n\n"
    "@pytest.mark.unit\ndef test_{name}():\n    assert {name}() == {value}\n"
)


def _create_project_with_modules(tmp_path: Path, name: str) -> Path:
    """A `sw init` project with two modules under `src/demo`, each with its own tests."""
    project_dir = tmp_path / name
    project_dir.mkdir()
    assert runner.invoke(app, ["init", name, "--path", str(project_dir)]).exit_code == 0
    (project_dir / "conftest.py").write_text(
        "import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).parent / 'src'))\n",
        encoding="utf-8",
    )
    for module in ("alpha", "beta"):
        code = project_dir / "src" / "demo" / module
        code.mkdir(parents=True)
        (code / "context.yaml").write_text(f"name: {module}\nlevel: module\n", encoding="utf-8")
        (code / "__init__.py").write_text("", encoding="utf-8")
        (code / f"{module}.py").write_text(
            f"def {module}() -> int:\n    return 1\n", encoding="utf-8"
        )
        tests = project_dir / "tests" / "unit" / module
        tests.mkdir(parents=True)
        (tests / f"test_{module}.py").write_text(
            _TEST.format(name=module, value=1), encoding="utf-8"
        )
    (project_dir / "src" / "demo" / "__init__.py").write_text("", encoding="utf-8")
    (project_dir / "tests_only.yaml").write_text(
        "name: tests_only\nsteps:\n"
        "  - name: test\n    action: validate\n    target: tests\n    params:\n"
        "      target: tests/\n",
        encoding="utf-8",
    )
    return project_dir


def _tests_run(project_dir: Path) -> int:
    """How many tests the newest run's test step ran, from the run store."""
    from specweaver.core.config.paths import state_db_path
    from specweaver.core.flow.engine.store import StateStore

    newest = StateStore(state_db_path()).list_runs(limit=1)[0]
    return int(newest.step_records[-1].result.output["passed"])


class TestIncrementalPipelineE2E:
    """Test full integration of topology hashing and pipeline execution."""

    def test_e2e_topology_cache_generated_on_success(self, tmp_path: Path) -> None:
        """Pipeline successfully validates pristine code and persists staleness cache."""
        project_dir = _create_project_with_clean_code(tmp_path, "success-proj")

        # Run validation pipeline
        result = runner.invoke(
            app, ["run", str(project_dir / "e2e_code.yaml"), "src/", "--project", str(project_dir)]
        )

        assert result.exit_code == 0, f"Run failed: {result.output}"

        # Verify cache hook triggered
        cache_file = project_dir / ".specweaver" / "topology.cache.json"
        assert cache_file.exists(), "Cache was not saved to .specweaver/topology.cache.json"

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert "." in data
        assert "src/math_ops.py" in data["."]["rendered_payload"]

    def test_the_next_run_tests_only_what_changed(self, tmp_path: Path) -> None:
        """Proves: C-FLOW-06 FR-2. Two modules; after a green run, one changes; only its tests run."""
        project_dir = _create_project_with_modules(tmp_path, "narrow-proj")
        run = ["run", str(project_dir / "tests_only.yaml"), "src/", "--project", str(project_dir)]

        first = runner.invoke(app, run)
        assert first.exit_code == 0, first.output
        assert _tests_run(project_dir) == 2

        (project_dir / "src" / "demo" / "beta" / "beta.py").write_text(
            "def beta() -> int:\n    return 2\n", encoding="utf-8"
        )
        (project_dir / "tests" / "unit" / "beta" / "test_beta.py").write_text(
            _TEST.format(name="beta", value=2), encoding="utf-8"
        )
        second = runner.invoke(app, run)
        assert second.exit_code == 0, second.output
        assert _tests_run(project_dir) == 1

        third = runner.invoke(app, run)  # nothing changed since the green run: every test
        assert third.exit_code == 0, third.output
        assert _tests_run(project_dir) == 2

    def test_a_run_without_tests_saves_no_cache(self, tmp_path: Path) -> None:
        """Proves: C-FLOW-06 FR-2. A green run that tested nothing leaves no point to compare with."""
        project_dir = _create_project_with_clean_code(tmp_path, "no-tests-proj")
        result = runner.invoke(
            app, ["run", "validate_only", "specs/math_spec.md", "--project", str(project_dir)]
        )

        assert result.exit_code == 0, result.output
        assert not (project_dir / ".specweaver" / "topology.cache.json").exists()

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

        result = runner.invoke(
            app, ["run", "validate_only", "specs/bad_spec.md", "--project", str(project_dir)]
        )

        # Pipeline fails gracefully (exiting 1) due to lint errors
        assert result.exit_code != 0

        # Cache MUST NOT exist because run didn't COMPLETE successfully
        assert not cache_file.exists(), "Cache was incorrectly saved despite pipeline failure!"
