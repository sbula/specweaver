# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
# fr-coverage: fixture-data

"""A batch of mutants, one sandbox, and a report ordered by what needs a decision.

`_mutate.py` answers one question at a time. A campaign asks a list of them in one sandbox and
writes the answers somewhere you can act on. Nothing is committed — the report is an **input to a
decision, never a record of one** (`AD-1`: the matrix is a document, not a checker).

The report's ordering is the design. Input order is useless; what matters is that the top of the
file is the work: what survived, then what only one test protects, then what could not be judged at
all. `KILLED` by several is a one-line footnote — there is nothing to do about it.
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


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "_mutate_campaign.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location("_mutate_campaign", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_mutate_campaign"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def camp() -> ModuleType:
    return _load()


def _mutant(**over):
    base = {"file": "src/a.py", "old": "x = 1", "new": "x = 2", "claim": "C1 — a thing"}
    return {**base, **over}


class TestLoadCampaign:
    """`load_campaign` — a mutant the runner cannot act on is refused before the sandbox is built."""

    def test_a_well_formed_campaign_loads(self, camp: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "c.json"
        path.write_text(json.dumps([_mutant()]), encoding="utf-8")
        assert camp.load_campaign(path) == [_mutant()]

    @pytest.mark.parametrize("missing", ["file", "old", "new", "claim"])
    def test_a_missing_key_is_refused(self, camp: ModuleType, tmp_path: Path, missing: str) -> None:
        entry = _mutant()
        del entry[missing]
        path = tmp_path / "c.json"
        path.write_text(json.dumps([entry]), encoding="utf-8")
        with pytest.raises(ValueError, match=missing):
            camp.load_campaign(path)

    def test_claim_is_required_because_a_verdict_without_one_is_unusable(
        self, camp: ModuleType, tmp_path: Path
    ) -> None:
        """A SURVIVED with no claim tells you a line is unprotected and not why you care."""
        path = tmp_path / "c.json"
        path.write_text(json.dumps([_mutant(claim="")]), encoding="utf-8")
        with pytest.raises(ValueError, match="claim"):
            camp.load_campaign(path)

    def test_an_empty_campaign_is_refused(self, camp: ModuleType, tmp_path: Path) -> None:
        path = tmp_path / "c.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            camp.load_campaign(path)


_RESULTS: list[dict[str, object]] = [
    {**_mutant(claim="C9 — healthy"), "verdict": "KILLED", "killers": ["t::a", "t::b"]},
    {**_mutant(claim="C1 — unprotected"), "verdict": "SURVIVED", "killers": []},
    {**_mutant(claim="C4 — bad anchor"), "verdict": "BROKEN", "killers": []},
    {**_mutant(claim="C7 — lone guard"), "verdict": "KILLED", "killers": ["t::only"]},
]
_META: dict[str, object] = {
    "head": "abc1234",
    "dirty": True,
    "mode": "FULL",
    "seconds": 581,
    "not_run": 2,
}


class TestRenderReport:
    """`render_report` — ordered by what needs a decision, and honest about its own gaps."""

    def test_survived_comes_first(self, camp: ModuleType) -> None:
        body = camp.render_report(_RESULTS, _META)
        order = [body.index(k) for k in ("SURVIVED", "KILLED x1", "BROKEN")]
        assert order == sorted(order), body

    def test_a_lone_protector_is_called_out_separately_from_healthy_kills(
        self, camp: ModuleType
    ) -> None:
        """The whole reason to pay for full runs: `KILLED x1` must not read as `KILLED`."""
        body = camp.render_report(_RESULTS, _META)
        assert "KILLED x1" in body
        assert "t::only" in body

    def test_the_header_states_what_makes_it_reproducible(self, camp: ModuleType) -> None:
        body = camp.render_report(_RESULTS, _META)
        for fact in ("abc1234", "DIRTY", "FULL"):
            assert fact in body, fact

    def test_it_states_what_was_not_run(self, camp: ModuleType) -> None:
        """A report that omits its own gaps reads as 'all clear' when it is not."""
        body = camp.render_report(_RESULTS, _META)
        assert "NOT RUN" in body
        assert "2" in body.split("NOT RUN")[1][:40]

    def test_every_claim_appears(self, camp: ModuleType) -> None:
        body = camp.render_report(_RESULTS, _META)
        for row in _RESULTS:
            assert row["claim"] in body, row["claim"]

    def test_a_clean_tree_says_so(self, camp: ModuleType) -> None:
        body = camp.render_report(_RESULTS, {**_META, "dirty": False})
        assert "CLEAN" in body
