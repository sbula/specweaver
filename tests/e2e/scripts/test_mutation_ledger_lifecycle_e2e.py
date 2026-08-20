# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A finding's whole life, driven through the command line.

Stories 6 and 7. The ledger is the only part of this tool committed to git, and nothing proved a
real session leaves a valid one — the matrix said e2e did not apply, which was wrong for the
durable artefact of the whole system.

Every other test builds a record or a ledger by hand. This runs the real session, against a real
corpus file, and then asks the real gate what it thinks. It is the only place the four pieces —
corpus, session record, ledger and gate — are all genuine at once.

The mutant carries an anchor that cannot be found, which is the cheapest deterministic way to
produce a finding: no test has to fail, and the run does not depend on any particular coverage
gap existing in the repo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

pytestmark = pytest.mark.e2e

MUTANT_ID = "F-LEDGER-01 FR-1 anchor-that-cannot-apply"
REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    """The real CLI module, loaded the way the timer loads it."""
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("mutation", REPO_ROOT / "scripts" / "mutation.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mutation"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    path = tmp_path / "F-LEDGER-01_mutants.json"
    path.write_text(
        json.dumps(
            {
                "schema": 1,
                "feature": "F-LEDGER-01",
                "campaigns": [
                    {
                        "requirement": "FR-1",
                        "title": "a finding that is deterministic",
                        "scope": ["tests/unit/scripts/test_mutate.py"],
                        "mutants": [
                            {
                                "id": "anchor-that-cannot-apply",
                                "file": "scripts/_mutate.py",
                                "symbol": "killers",
                                "old": "THIS ANCHOR DOES NOT EXIST ANYWHERE",
                                "new": "nor does this",
                                "breaks": "nothing — the anchor cannot be applied",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _run(mutation: ModuleType, corpus: Path, out: Path, ledger: Path) -> int:
    return mutation.main(
        [
            "--corpus",
            str(corpus),
            "--no-baseline",
            "--out",
            str(out),
            "--ledger",
            str(ledger),
        ]
    )


class TestLedgerLifecycle:
    def test_a_real_session_leaves_a_ledger_in_the_declared_shape(
        self, mutation: ModuleType, corpus: Path, tmp_path: Path
    ) -> None:
        """Story 6. Nothing else asserts the committed artefact is well-formed."""
        out, ledger = tmp_path / "record.json", tmp_path / "ledger.json"

        _run(mutation, corpus, out, ledger)

        data = json.loads(ledger.read_text(encoding="utf-8"))
        assert data["schema"] == 1
        entry = data["findings"][MUTANT_ID]
        assert entry["occurrences"] == 1
        assert entry["first_seen"] == entry["last_seen"]
        assert entry["history"][-1]["state"] == "open"
        assert entry["history"][-1]["verdict"] == "UNMEASURED"

    def test_the_current_state_is_not_stored_beside_the_history(
        self, mutation: ModuleType, corpus: Path, tmp_path: Path
    ) -> None:
        """The contract's central rule, checked on a real artefact rather than a fixture."""
        out, ledger = tmp_path / "record.json", tmp_path / "ledger.json"

        _run(mutation, corpus, out, ledger)

        entry = json.loads(ledger.read_text(encoding="utf-8"))["findings"][MUTANT_ID]
        assert "verdict" not in entry
        assert "closed_at" not in entry

    def test_a_finding_blocks_the_gate_until_a_human_answers_it(
        self, mutation: ModuleType, corpus: Path, tmp_path: Path
    ) -> None:
        """Story 7, first half."""
        out, ledger = tmp_path / "record.json", tmp_path / "ledger.json"
        _run(mutation, corpus, out, ledger)

        blocked = mutation.main(["--gate", "--out", str(out), "--ledger", str(ledger)])

        assert blocked == 1, "an unanswered finding must block"

    def test_confirming_through_the_cli_clears_it(
        self, mutation: ModuleType, corpus: Path, tmp_path: Path
    ) -> None:
        """Story 7, second half — and the disposition must land in the history, with its date."""
        out, ledger = tmp_path / "record.json", tmp_path / "ledger.json"
        _run(mutation, corpus, out, ledger)

        mutation.main(
            [
                "--confirm",
                MUTANT_ID,
                "--as",
                "fixed-campaign",
                "--why",
                "the anchor was wrong",
                "--ledger",
                str(ledger),
            ]
        )
        cleared = mutation.main(["--gate", "--out", str(out), "--ledger", str(ledger)])

        assert cleared == 0
        disposed = [
            h
            for h in json.loads(ledger.read_text(encoding="utf-8"))["findings"][MUTANT_ID][
                "history"
            ]
            if h["state"] == "disposed"
        ]
        assert disposed[-1]["disposition"] == "fixed-campaign"
        assert disposed[-1]["at"]

    def test_a_second_session_does_not_grow_the_history(
        self, mutation: ModuleType, corpus: Path, tmp_path: Path
    ) -> None:
        """Append-on-change, on the real path. Otherwise a nightly adds a line every night for
        ever and the file this design bounded grows without limit."""
        out, ledger = tmp_path / "record.json", tmp_path / "ledger.json"
        _run(mutation, corpus, out, ledger)
        before = len(
            json.loads(ledger.read_text(encoding="utf-8"))["findings"][MUTANT_ID]["history"]
        )

        _run(mutation, corpus, out, ledger)

        entry = json.loads(ledger.read_text(encoding="utf-8"))["findings"][MUTANT_ID]
        assert len(entry["history"]) == before
        assert entry["occurrences"] == 2, "it still counts, it just does not narrate"
