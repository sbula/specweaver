# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A session's tree fingerprint ignores the findings ledger the session itself writes.

Proves: TECH-049 FR-11

Every run writes `scripts/baselines/mutation_findings.json` after it has stamped the tree. With the
ledger in the fingerprint, the tree changed under every verdict, so the morning gate blocked every
nightly as "measured over uncommitted work that is no longer in the tree" — and nobody read the
findings behind it (found 2026-10-15).

| Bucket | Case |
|---|---|
| Happy | a change to a source file changes the fingerprint |
| Boundary | a clean tree, and the same tree with only the ledger changed, match |
| Degradation | a new untracked file changes it |
| Hostile | a file named like the ledger in another folder still counts |
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
_LEDGER = "scripts/baselines/mutation_findings.json"


@pytest.fixture(scope="module")
def reach() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_run_reach", REPO_ROOT / "scripts" / "_run_reach.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_run_reach"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path: Path, reach: ModuleType) -> Path:
    run = reach._mutate._run
    for rel, text in {
        _LEDGER: "{}\n",
        "a.py": "x = 1\n",
        "other/mutation_findings.json": "{}\n",
    }.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text, encoding="utf-8")
    run(["git", "init", "-q"], tmp_path)
    run(["git", "add", "-A"], tmp_path)
    run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c"], tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    ("rel", "same"),
    [(_LEDGER, True), ("a.py", False), ("new.py", False), ("other/mutation_findings.json", False)],
)
def test_only_the_ledger_is_left_out(reach: ModuleType, repo: Path, rel: str, same: bool) -> None:
    clean = reach.tree_sha(repo)
    (repo / rel).write_text('{"changed": true}\n', encoding="utf-8")

    assert (reach.tree_sha(repo) == clean) is same


@pytest.mark.parametrize(("rel", "dirty"), [(_LEDGER, False), ("a.py", True), ("new.py", True)])
def test_only_the_ledger_leaves_the_tree_clean(
    reach: ModuleType, repo: Path, rel: str, dirty: bool
) -> None:
    assert reach.is_dirty(repo) is False
    (repo / rel).write_text('{"changed": true}\n', encoding="utf-8")

    assert reach.is_dirty(repo) is dirty
