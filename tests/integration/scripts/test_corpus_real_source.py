# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The corpus, exercised against this repository's own source rather than a fixture.

Proves: TECH-049 FR-2, FR-13

Every unit test for `_corpus.py` builds its own tiny module, which proves the algorithm and
nothing about whether it survives real code — decorators, annotations, `__future__` imports,
nested classes. This pins a mutant against a file in `src/specweaver/` and asserts the round trip,
so a hashing change that only works on toy input fails here.

Integration tier because the seam is the real tree: the moment `src/` moves, `scanner.py` is
renamed or `check_lineage` is refactored, this test says so. That is the point — it is the same
`STALE` signal the corpus exists to raise, aimed at itself.
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
TARGET = "src/specweaver/graph/lineage/scanner.py"


@pytest.fixture(scope="module")
def corpus() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_corpus.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_corpus", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_corpus"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def real_corpus_file(tmp_path: Path) -> Path:
    body = {
        "schema": 2,
        "feature": "D-SENS-09",
        "campaigns": [
            {
                "requirement": "FR-97",
                "scope": ["tests/unit/graph/interfaces/test_cli_lineage.py"],
                "mutants": [
                    {
                        "id": "orphans-empty",
                        "origin": "authored",
                        "file": TARGET,
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
class TestCorpusAgainstRealSource:
    """Hashing, drift and anchor checks against production code."""

    def test_the_target_still_exists(self) -> None:
        """Guards the rest of this file from passing vacuously if the fixture drifts."""
        assert (REPO_ROOT / TARGET).is_file(), f"fixture drifted: {TARGET} is gone"

    def test_refresh_pins_a_real_symbol_and_drift_reports_ok(
        self, corpus: ModuleType, real_corpus_file: Path
    ) -> None:
        sha = corpus.refresh(real_corpus_file, "D-SENS-09 FR-97 orphans-empty", REPO_ROOT)
        assert sha.startswith("sha256:")
        mutant = corpus.load_corpus(real_corpus_file).campaigns[0].mutants[0]
        assert corpus.drift_of(mutant, REPO_ROOT) == "OK"

    def test_the_anchor_resolves_inside_the_real_symbol(self, corpus: ModuleType) -> None:
        """Rule 9 against production source, where `return []` is not file-unique."""
        source = (REPO_ROOT / TARGET).read_text(encoding="utf-8")
        corpus.check_anchor(source, "check_lineage", "return sorted(orphans)")
