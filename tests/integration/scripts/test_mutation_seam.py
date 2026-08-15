# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The first place the corpus and the runner meet.

Proves: TECH-049 FR-4

`SF-01` produced validated `Corpus` objects and ran nothing; `_mutate` ran mutants and knew nothing
about campaigns. This is the seam between them, and per `ADR-003` it belongs to the boundary that
creates it — there is no later story that would write it.

Integration tier because it builds a real detached worktree and runs real pytest. That is the cost
of the only test that proves the two halves fit; everything else about them is already unit-tested.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    return _load("mutation")


@pytest.fixture(scope="module")
def corpus() -> ModuleType:
    return _load("_corpus")


@pytest.fixture
def corpus_file(tmp_path: Path) -> Path:
    """A campaign whose mutant neutralises orphan detection, scoped to the tests that cover it."""
    body = {
        "schema": 1,
        "feature": "D-SENS-09",
        "campaigns": [
            {
                "requirement": "FR-97",
                "scope": ["tests/unit/graph/interfaces/test_cli_lineage.py"],
                "mutants": [
                    {
                        "id": "orphans-empty",
                        "file": "src/specweaver/graph/lineage/scanner.py",
                        "symbol": "check_lineage",
                        "old": "return sorted(orphans)",
                        "new": "return []",
                        "breaks": "orphan detection reports nothing",
                    }
                ],
            }
        ],
    }
    path = tmp_path / "D-SENS-09_mutants.json"
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


@pytest.mark.integration
class TestCorpusDrivesTheRunner:
    """A `Corpus` from SF-01, executed by `_mutate` in a real sandbox."""

    def test_a_corpus_mutant_is_killed_by_its_scoped_tests(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path
    ) -> None:
        loaded = corpus.load_corpus(corpus_file)
        results = mutation.run_corpus(loaded, baseline=None)

        assert len(results) == 1, "one mutant declared, one result expected"
        only = results[0]
        assert only.outcome == "KILL"
        assert only.derived_id == "D-SENS-09 FR-97 orphans-empty"
        assert any("test_check_lineage_detects_orphans" in k for k in only.killers)

    def test_a_mistyped_scope_is_not_a_survival(
        self, mutation: ModuleType, corpus: ModuleType, corpus_file: Path
    ) -> None:
        """`FR-4` end to end — the false negative this sub-feature exists to close.

        Before the exit-code guard, a scope pointing at nothing collected zero tests, produced zero
        failures, and was reported as a survival: a finding saying the requirement is unprotected
        when in truth nothing was measured at all.
        """
        data = json.loads(corpus_file.read_text(encoding="utf-8"))
        data["campaigns"][0]["scope"] = ["tests/unit/graph/interfaces/test_typo_does_not_exist.py"]
        corpus_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        results = mutation.run_corpus(corpus.load_corpus(corpus_file), baseline=None)
        assert results[0].outcome == "NOTHING_RAN"
        assert results[0].outcome != "NO_KILL"
