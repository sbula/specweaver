# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Who wrote a mutant, and what that licenses it to leave out.

Stage E of the mutation data contract. Every mutant in the corpus today was written by a person,
including its `breaks` line — the plain-words statement of the bug being planted, without which a
survival is unreadable. `A-VAL-03` plans mutants generated from an AST, and a generated mutant
cannot supply that sentence.

So the schema records **who made it**. A reader finding no `breaks` on an authored mutant has found
an authoring omission; on a derived one, they have found the expected state. Those are opposite
conclusions and the file has to be able to tell them apart — which is the whole reason to add this
before generation exists, rather than after.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def corpus() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_corpus", REPO_ROOT / "scripts" / "_corpus.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_corpus"] = module
    spec.loader.exec_module(module)
    return module


def _mutant(**over: Any) -> dict[str, Any]:
    base = {
        "id": "slug",
        "origin": "authored",
        "file": "scripts/_mutate.py",
        "symbol": "killers",
        "old": "a",
        "new": "b",
        "breaks": "nothing objects",
    }
    return {**base, **over}


def _file(tmp_path: Path, *mutants: dict[str, Any], schema: int = 2) -> Path:
    path = tmp_path / "F-TEST-01_mutants.json"
    path.write_text(
        json.dumps(
            {
                "schema": schema,
                "feature": "F-TEST-01",
                "campaigns": [
                    {
                        "requirement": "FR-1",
                        "title": "t",
                        "scope": ["tests/unit/scripts/test_mutate.py"],
                        "mutants": list(mutants),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


class TestLoadCorpusOrigin:
    """The field itself."""

    def test_an_authored_mutant_carries_its_origin(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        loaded = corpus.load_corpus(_file(tmp_path, _mutant()))

        assert loaded.campaigns[0].mutants[0].origin == "authored"

    def test_a_derived_mutant_needs_no_breaks(self, corpus: ModuleType, tmp_path: Path) -> None:
        """A generator has no plain-words account of the bug it planted, and demanding one would
        force it to invent a sentence nobody wrote."""
        loaded = corpus.load_corpus(_file(tmp_path, _mutant(origin="derived", breaks=None)))

        assert loaded.campaigns[0].mutants[0].breaks is None

    def test_an_authored_mutant_without_breaks_is_refused(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        """The control, and the reason the field exists. Silence from a person is an omission;
        silence from a generator is the expected state. Without `origin` they are the same file."""
        with pytest.raises(corpus.CorpusError, match="breaks"):
            corpus.load_corpus(_file(tmp_path, _mutant(breaks=None)))

    def test_an_unknown_origin_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """[Hostile] A typo must not create a third provenance nobody has rules for."""
        with pytest.raises(corpus.CorpusError, match="origin"):
            corpus.load_corpus(_file(tmp_path, _mutant(origin="borrowed")))

    def test_a_missing_origin_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """Defaulting to `authored` would let a generated corpus claim a person wrote it."""
        raw = _mutant()
        del raw["origin"]

        with pytest.raises(corpus.CorpusError, match="origin"):
            corpus.load_corpus(_file(tmp_path, raw))


class TestLoadCorpusSchema:
    """The reader says which shape it understands."""

    def test_schema_two_is_accepted(self, corpus: ModuleType, tmp_path: Path) -> None:
        assert corpus.load_corpus(_file(tmp_path, _mutant())).campaigns

    def test_schema_one_is_refused_with_a_readable_reason(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        """[Graceful] A corpus written for the old reader must say so plainly rather than failing
        on a missing key three frames down."""
        raw = _mutant()
        del raw["origin"]

        with pytest.raises(corpus.CorpusError, match="schema"):
            corpus.load_corpus(_file(tmp_path, raw, schema=1))


class TestLoadCorpusOnTheRealTree:
    """The tree itself, so a half-migrated corpus cannot pass."""

    def test_every_campaign_file_declares_the_current_schema(self, corpus: ModuleType) -> None:
        for path in sorted((REPO_ROOT / "docs" / "roadmap" / "features").rglob("*_mutants.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            assert data["schema"] == corpus.SCHEMA, f"{path.name} is still schema {data['schema']}"

    def test_every_mutant_declares_its_origin(self, corpus: ModuleType) -> None:
        for path in sorted((REPO_ROOT / "docs" / "roadmap" / "features").rglob("*_mutants.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for campaign in data["campaigns"]:
                for mutant in campaign["mutants"]:
                    assert mutant.get("origin") in {"authored", "derived"}, (
                        f"{path.name}:{mutant['id']} has no origin"
                    )

    def test_the_whole_corpus_still_loads(self, corpus: ModuleType) -> None:
        """The control on the migration: valid JSON with the right keys is not the same as a
        corpus the reader accepts."""
        for path in sorted((REPO_ROOT / "docs" / "roadmap" / "features").rglob("*_mutants.json")):
            assert corpus.load_corpus(path).campaigns, f"{path.name} loaded no campaigns"
