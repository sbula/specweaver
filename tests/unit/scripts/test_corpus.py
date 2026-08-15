# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""The mutation campaign corpus — load it, or refuse it loudly.

Proves: TECH-049 FR-1, FR-1a

A campaign targets one (N)FR and holds several mutants that each try to break it. The corpus is
version-controlled beside the design it tests, so a malformed file must fail at parse time rather
than after a sandbox has been built — `_mutate_campaign.load_campaign` established that order and
this keeps it.

Two rules here are not obvious and are the reason most of these stories exist:

* **The derived id is the mutant's identity across runs.** `FR-11a` recurrence counts and `FR-12`
  override entries have to name the same mutant tonight and next month, and a hand-typed id drifts.
  It is composed, never accepted.
* **`feature` must match the filename**, which is what lets rule 6 be a single-file check: two
  corpus files cannot claim the same feature, so a cross-file id collision is impossible by
  construction rather than by luck.
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


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_corpus.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_corpus", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_corpus"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def corpus() -> ModuleType:
    return _load()


def _mutant(**over: Any) -> dict[str, Any]:
    base = {
        "id": "isolation-off",
        "file": "src/specweaver/x.py",
        "symbol": "apply_session_policy",
        "old": "return policy.enabled",
        "new": "return False",
        "breaks": "no worktree is created",
    }
    return {**base, **over}


def _campaign(**over: Any) -> dict[str, Any]:
    base = {
        "requirement": "FR-8",
        "title": "Worktree-bounded multi-step e2e",
        "scope": ["tests/e2e/sandbox/test_session_worktree_isolation_e2e.py"],
        "mutants": [_mutant()],
    }
    return {**base, **over}


def _write(tmp_path: Path, feature: str = "C-EXEC-06", **over: Any) -> Path:
    """A corpus file named the way the loader expects: `<ID>_mutants.json`."""
    body: dict[str, Any] = {"schema": 1, "feature": feature, "campaigns": [_campaign()]}
    body.update(over)
    path = tmp_path / f"{feature}_mutants.json"
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return path


class TestLoadCorpus:
    """A well-formed corpus loads, and its mutants carry a composed identity."""

    def test_a_valid_corpus_loads_its_campaigns(self, corpus: ModuleType, tmp_path: Path) -> None:
        loaded = corpus.load_corpus(_write(tmp_path))
        assert loaded.feature == "C-EXEC-06"
        assert [c.requirement for c in loaded.campaigns] == ["FR-8"]
        assert [m.id for m in loaded.campaigns[0].mutants] == ["isolation-off"]

    def test_the_mutant_id_is_derived_not_taken(self, corpus: ModuleType, tmp_path: Path) -> None:
        """`FR-1a` — identity is composed from feature + requirement + local id.

        Asserted against a literal rather than by re-composing it from the loaded object, which
        would only prove the loader agrees with itself.
        """
        loaded = corpus.load_corpus(_write(tmp_path))
        assert loaded.campaigns[0].mutants[0].derived_id == "C-EXEC-06 FR-8 isolation-off"

    def test_two_campaigns_both_load(self, corpus: ModuleType, tmp_path: Path) -> None:
        second = _campaign(requirement="FR-9", mutants=[_mutant(id="policy-null")])
        path = _write(tmp_path, campaigns=[_campaign(), second])
        loaded = corpus.load_corpus(path)
        assert [c.requirement for c in loaded.campaigns] == ["FR-8", "FR-9"]


class TestLoadCorpusBoundaries:
    """Empty collections, and the states that are legal but easy to mistake for errors."""

    def test_an_empty_mutant_list_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        path = _write(tmp_path, campaigns=[_campaign(mutants=[])])
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_an_empty_scope_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """A campaign with no scope would run its mutants against nothing and read as a survival."""
        path = _write(tmp_path, campaigns=[_campaign(scope=[])])
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_a_retired_campaign_loads_and_is_marked(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        """Retire marks, never deletes — the record that it was measured has to survive."""
        retired = _campaign(retired={"reason": "requirement descoped", "date": "2026-08-15"})
        loaded = corpus.load_corpus(_write(tmp_path, campaigns=[retired]))
        assert loaded.campaigns[0].retired is not None
        assert loaded.campaigns[0].retired["reason"] == "requirement descoped"

    def test_a_missing_symbol_sha_is_legal(self, corpus: ModuleType, tmp_path: Path) -> None:
        """The normal authoring flow: a human writes a mutant without knowing the hash.

        Absent is `UNHASHED`, not `STALE`, and never an error — otherwise every newly authored
        mutant would be born invalid and the corpus could not grow.
        """
        loaded = corpus.load_corpus(_write(tmp_path))
        assert loaded.campaigns[0].mutants[0].symbol_sha is None

    def test_a_recorded_symbol_sha_is_kept(self, corpus: ModuleType, tmp_path: Path) -> None:
        pinned = _campaign(mutants=[_mutant(symbol_sha="sha256:abc")])
        loaded = corpus.load_corpus(_write(tmp_path, campaigns=[pinned]))
        assert loaded.campaigns[0].mutants[0].symbol_sha == "sha256:abc"


class TestLoadCorpusDegradation:
    """Unreadable or unknown input fails at parse time, before any sandbox work."""

    def test_an_unknown_schema_is_refused_naming_the_version(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, schema=99)
        with pytest.raises(corpus.CorpusError, match="99"):
            corpus.load_corpus(path)

    def test_malformed_json_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "C-EXEC-06_mutants.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_a_missing_file_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(tmp_path / "C-EXEC-06_mutants.json")

    @pytest.mark.parametrize("key", ["requirement", "scope", "mutants"])
    def test_a_campaign_missing_a_key_is_refused(
        self, corpus: ModuleType, tmp_path: Path, key: str
    ) -> None:
        broken = {k: v for k, v in _campaign().items() if k != key}
        path = _write(tmp_path, campaigns=[broken])
        with pytest.raises(corpus.CorpusError, match=key):
            corpus.load_corpus(path)

    @pytest.mark.parametrize("key", ["id", "file", "symbol", "old", "new", "breaks"])
    def test_a_mutant_missing_a_key_is_refused(
        self, corpus: ModuleType, tmp_path: Path, key: str
    ) -> None:
        broken = {k: v for k, v in _mutant().items() if k != key}
        path = _write(tmp_path, campaigns=[_campaign(mutants=[broken])])
        with pytest.raises(corpus.CorpusError, match=key):
            corpus.load_corpus(path)


class TestLoadCorpusHostileInput:
    """The three ways a corpus can be well-formed JSON and still be a lie."""

    def test_an_identical_replacement_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """`old == new` mutates nothing, so the run would report a false survival."""
        same = _campaign(mutants=[_mutant(new="return policy.enabled")])
        path = _write(tmp_path, campaigns=[same])
        with pytest.raises(corpus.CorpusError):
            corpus.load_corpus(path)

    def test_a_duplicate_derived_id_is_refused(self, corpus: ModuleType, tmp_path: Path) -> None:
        """Two mutants resolving to one identity would collapse into each other across runs.

        Recurrence counts and override entries address a mutant by this string; if two answer to
        it, one silently inherits the other's history.
        """
        twin = _campaign(mutants=[_mutant(), _mutant(new="return None")])
        path = _write(tmp_path, campaigns=[twin])
        with pytest.raises(corpus.CorpusError, match="isolation-off"):
            corpus.load_corpus(path)

    def test_a_feature_disagreeing_with_the_filename_is_refused(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        """This is what makes the uniqueness check a single-file check.

        If a file may declare any feature, two files can claim the same one and a duplicate id
        across them becomes invisible without loading the whole corpus.
        """
        path = tmp_path / "C-EXEC-06_mutants.json"
        body = {"schema": 1, "feature": "B-INTL-09", "campaigns": [_campaign()]}
        path.write_text(json.dumps(body), encoding="utf-8")
        with pytest.raises(corpus.CorpusError, match="B-INTL-09"):
            corpus.load_corpus(path)


class TestLoadCorpusErrorMessages:
    """A message that says only 'missing key' costs the reader a search (R-2)."""

    def test_a_failure_names_the_file_the_campaign_and_the_mutant(
        self, corpus: ModuleType, tmp_path: Path
    ) -> None:
        broken = {k: v for k, v in _mutant().items() if k != "old"}
        path = _write(tmp_path, campaigns=[_campaign(mutants=[broken])])
        with pytest.raises(corpus.CorpusError) as caught:
            corpus.load_corpus(path)
        message = str(caught.value)
        assert "C-EXEC-06_mutants.json" in message
        assert "FR-8" in message
        assert "isolation-off" in message
