# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A test step over the whole project runs only the tests of the modules changed since the last
green test run, and of the modules that use them.

Proves: C-FLOW-06 FR-2

Real files, real hashes, real topology: the seam is the hash cache (A-SENS-01) read by the test
step's target resolution.

| Bucket | Case |
|---|---|
| Happy | one module changed: its tests only; a module others use changed: its tests and theirs |
| Boundary | nothing changed, or no cache: every test; a file of the root module changed: the tier |
| Degradation | a broken cache file: every test |
| Hostile | a test step on one folder is never widened or narrowed; code changed in the run's worktree counts |
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.assurance.graph.hasher import DependencyHasher
from specweaver.core.flow.handlers.run_context import IsolationPolicy, RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler
from specweaver.workspace.analyzers.factory import AnalyzerFactory

if TYPE_CHECKING:
    import pytest

_MODULES = {
    "alpha": [],
    "beta": [],
    "gamma": ["alpha"],  # gamma uses alpha
}


def _project(root: Path) -> Path:
    """A project as `sw init` lays it out: root and `src` boundaries above three modules."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "context.yaml").write_text("name: demo\nlevel: system\n", encoding="utf-8")
    (root / "README.md").write_text("demo\n", encoding="utf-8")
    src = root / "src"
    src.mkdir()
    (src / "context.yaml").write_text("name: src\nlevel: service\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "context.yaml").write_text("name: tests\nlevel: service\n", "utf-8")
    for name, consumes in _MODULES.items():
        module = src / "demo" / name
        module.mkdir(parents=True)
        (module / "context.yaml").write_text(
            f"name: {name}\nlevel: module\nconsumes: {consumes}\n", encoding="utf-8"
        )
        (module / f"{name}.py").write_text(f"def {name}() -> int:\n    return 1\n", "utf-8")
        (root / "tests" / "unit" / name).mkdir(parents=True)
    return root


def _green_run(root: Path) -> None:
    """What `sw run` leaves after a run whose tests passed."""
    DependencyHasher(root, AnalyzerFactory).save_cache()


def _targets(root: Path, target: str = "tests/", execution_root: Path | None = None) -> list[str]:
    context = RunContext(
        project_path=root,
        spec_path=root / "spec.md",
        isolation=IsolationPolicy(execution_root=execution_root),
    )
    return ValidateTestsHandler()._resolve_targets(context, target, "unit")


def _unit(*names: str) -> list[str]:
    return sorted(str(Path("tests") / "unit" / n) for n in names)


def test_one_changed_module_runs_only_its_tests(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    root = _project(tmp_path)
    _green_run(root)
    (root / "src" / "demo" / "beta" / "beta.py").write_text("def beta() -> int:\n    return 2\n")

    assert _targets(root) == _unit("beta")


def test_a_module_others_use_runs_their_tests_too(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    root = _project(tmp_path)
    _green_run(root)
    (root / "src" / "demo" / "alpha" / "alpha.py").write_text("def alpha() -> int:\n    return 9\n")

    assert _targets(root) == _unit("alpha", "gamma")


def test_a_changed_test_file_runs_its_own_folder(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    root = _project(tmp_path)
    _green_run(root)
    (root / "tests" / "unit" / "beta" / "test_beta.py").write_text("def test_b():\n    pass\n")

    assert _targets(root) == _unit("beta")


def test_code_and_its_test_changed_run_the_folder_once(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    (root / "src" / "demo" / "beta" / "beta.py").write_text("def beta() -> int:\n    return 2\n")
    (root / "tests" / "unit" / "beta" / "test_beta.py").write_text("def test_b():\n    pass\n")

    assert _targets(root) == _unit("beta")


def test_a_folder_inside_another_is_not_run_twice(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    (root / "README.md").write_text("changed\n", encoding="utf-8")
    (root / "src" / "demo" / "beta" / "beta.py").write_text("def beta() -> int:\n    return 2\n")

    assert _targets(root) == [str(Path("tests") / "unit")]


def test_a_test_of_another_tier_changed_runs_every_test(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    other = root / "tests" / "integration"
    other.mkdir()
    (other / "test_x.py").write_text("def test_x():\n    pass\n")

    assert _targets(root) == ["tests/"]


def test_a_new_file_counts_as_a_change(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    (root / "src" / "demo" / "beta" / "extra.py").write_text("X = 1\n")

    assert _targets(root) == _unit("beta")


def test_nothing_changed_runs_every_test(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    root = _project(tmp_path)
    _green_run(root)

    assert _targets(root) == ["tests/"]


def test_without_a_green_run_every_test_runs(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "src" / "demo" / "beta" / "beta.py").write_text("def beta() -> int:\n    return 2\n")

    assert _targets(root) == ["tests/"]


def test_a_broken_cache_runs_every_test(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    (root / ".specweaver" / "topology.cache.json").write_text("{not json", encoding="utf-8")
    (root / "src" / "demo" / "beta" / "beta.py").write_text("def beta() -> int:\n    return 2\n")

    assert _targets(root) == ["tests/"]


def test_a_file_of_the_root_module_runs_the_whole_tier(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    (root / "README.md").write_text("changed\n", encoding="utf-8")

    assert _targets(root) == [str(Path("tests") / "unit")]


def test_a_changed_module_without_a_test_folder_runs_the_whole_tier(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    (root / "tests" / "unit" / "beta").rmdir()
    (root / "src" / "demo" / "beta" / "beta.py").write_text("def beta() -> int:\n    return 2\n")

    assert _targets(root) == [str(Path("tests") / "unit")]


def test_a_step_on_one_folder_keeps_its_folder(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _green_run(root)
    (root / "src" / "demo" / "beta" / "beta.py").write_text("def beta() -> int:\n    return 2\n")

    assert _targets(root, target="tests/unit/alpha") == ["tests/unit/alpha"]


def test_code_changed_in_the_runs_worktree_counts(tmp_path: Path) -> None:
    # Proves: C-FLOW-06 FR-2
    root = _project(tmp_path / "repo")
    _green_run(root)
    worktree = tmp_path / "worktree"
    shutil.copytree(root, worktree, ignore=shutil.ignore_patterns(".specweaver"))
    (worktree / "src" / "demo" / "beta" / "beta.py").write_text(
        "def beta() -> int:\n    return 3\n"
    )

    assert _targets(root, execution_root=worktree) == _unit("beta")


class _PassingAtom:
    def run(self, intent: dict[str, object]) -> object:
        from specweaver.sandbox.base import AtomResult, AtomStatus

        return AtomResult(status=AtomStatus.SUCCESS, message="", exports={"total": 1, "passed": 1})


async def _flag(tmp_path: Path, target: str, monkeypatch: pytest.MonkeyPatch) -> object:
    from specweaver.core.flow.engine.models import PipelineStep

    root = _project(tmp_path)
    monkeypatch.setattr(ValidateTestsHandler, "_get_atom", lambda self, context: _PassingAtom())
    step = PipelineStep(name="t", action="validate", target="tests", params={"target": target})
    context = RunContext(project_path=root, spec_path=root / "spec.md")
    result = await ValidateTestsHandler().execute(step, context)
    return result.output["tests_cover_project"]


async def test_a_whole_project_test_step_says_it_covered_the_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Proves: C-FLOW-06 FR-2
    assert await _flag(tmp_path, "tests/", monkeypatch) is True


async def test_a_test_step_on_one_folder_says_it_did_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Proves: C-FLOW-06 FR-2
    assert await _flag(tmp_path, "tests/unit/alpha", monkeypatch) is False
