# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A scenario test runs in a real container from the `/scenarios` mount and leaves no trace.

Proves: B-FLOW-01 FR-14

A real Podman or Docker engine, and SpecWeaver's own sandbox image, built here when missing.

| Bucket | Case |
|---|---|
| Happy | a scenario test in the mount runs and passes |
| Boundary | the code under test is found at `/workspace` from the mount |
| Degradation | not applicable — without an engine this file is skipped, and the dual run refuses |
| Hostile | no file outside the scenario folder names the scenario test; the scratch is removed |
"""

from __future__ import annotations

import gc
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution.sandbox_image import container_available
from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    not container_available(), reason="no live podman/docker engine on this host"
)

_TEST = "test_greet_scenarios.py"


def _project(root: Path) -> Path:
    (root / "src").mkdir(parents=True)
    (root / "scenarios" / "generated").mkdir(parents=True)
    (root / "src" / "greet.py").write_text("def greet():\n    return 'hi'\n", encoding="utf-8")
    (root / "scenarios" / "generated" / _TEST).write_text(
        "import importlib.util\nfrom pathlib import Path\n\n"
        "_ROOT = Path('/workspace')\n"
        "spec = importlib.util.spec_from_file_location('t', _ROOT / 'src' / 'greet.py')\n"
        "module = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n\n\n"
        "def test_greets():\n    assert module.greet() == 'hi'\n",
        encoding="utf-8",
    )
    return root


def test_a_scenario_test_runs_from_the_mount_and_leaves_no_trace(tmp_path: Path) -> None:
    project = _project(tmp_path / "project")
    atom = QARunnerAtom(cwd=project, scenarios_root=project / "scenarios")
    scratch = atom._runner._executor._mounts.scratch_root

    result = atom.run(
        {
            "intent": "run_tests",
            "target": f"/scenarios/generated/{_TEST}",
            "kind": "",
            "timeout": 600,
        }
    )

    assert result.status.value == "SUCCESS", result.message
    assert result.exports["passed"] == 1
    assert not scratch.is_relative_to(project)
    traces = [
        p
        for p in project.rglob("*")
        if p.is_file()
        and "scenarios" not in p.relative_to(project).parts[:1]
        and "test_greet_scenarios" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert traces == []

    del atom, result
    gc.collect()
    assert not scratch.exists()
