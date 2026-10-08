# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step's limit is the chosen percentile of the newest passed steps of its group.

Proves: B-FLOW-07 FR-4, B-FLOW-07 FR-5

A real database, filled as SF-01 fills it: calls in `llm_usage_log`, outcomes in
`llm_step_outcome`.

| Bucket | Case |
|---|---|
| Happy | 10 passed steps → their 90% value, in tokens and in USD |
| Boundary | 9 passed steps → no limit; with more than 10, only the newest 10 count |
| Degradation | a step with an unpriced call is left out of a money history |
| Hostile | failed steps, other DALs and other models never join the group |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.infrastructure.llm.store import nearest_rank, step_history_limit

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_GROUP = {"task_type": "review", "model": "m", "dal_level": "DAL_C"}


@pytest.fixture
def db(tmp_path: Path) -> Database:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path)


def _step(
    db: Database,
    n: int,
    tokens: int,
    cost: float | None,
    *,
    outcome: str = "passed",
    dal: str = "DAL_C",
    model: str = "m",
) -> None:
    run, step = f"run-{n}", "review_it"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider, "
            "prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms, run_id, "
            "server, dal_level, step_name) VALUES (?, 'p', 'review', ?, 'x', 0, 0, ?, ?, 1, ?, "
            "'gb10', ?, ?)",
            (f"2026-10-08T10:{n:02d}:00+00:00", model, tokens, cost, run, dal, step),
        )
        conn.execute(
            "INSERT INTO llm_step_outcome (run_id, step_name, outcome) VALUES (?, ?, ?)",
            (run, step, outcome),
        )


def _limit(db: Database, unit: str = "tokens") -> float | None:
    return step_history_limit(db, **_GROUP, unit=unit, steps=10, percentile=90)


@pytest.mark.parametrize(
    ("values", "pct", "expected"), [([5, 1, 3], 50, 3), (list(range(1, 11)), 90, 9), ([7], 90, 7)]
)
def test_nearest_rank(values: list[int], pct: int, expected: int) -> None:
    assert nearest_rank(values, pct) == expected


def test_ten_passed_steps_give_their_90_percent_value(db: Database) -> None:
    for n in range(1, 11):
        _step(db, n, tokens=n * 100, cost=n * 0.1)

    assert _limit(db) == 900
    assert _limit(db, "usd") == pytest.approx(0.9)


def test_nine_passed_steps_give_no_limit(db: Database) -> None:
    for n in range(1, 10):
        _step(db, n, tokens=100, cost=0.1)

    assert _limit(db) is None


def test_only_the_newest_ten_count(db: Database) -> None:
    for n in range(1, 11):
        _step(db, n, tokens=10_000, cost=1.0)
    for n in range(11, 21):
        _step(db, n, tokens=100, cost=0.1)

    assert _limit(db) == 100


def test_other_groups_and_failed_steps_never_join(db: Database) -> None:
    for n in range(1, 10):
        _step(db, n, tokens=100, cost=0.1)
    _step(db, 10, tokens=100, cost=0.1, outcome="failed")
    _step(db, 11, tokens=100, cost=0.1, dal="DAL_A")
    _step(db, 12, tokens=100, cost=0.1, model="other")

    assert _limit(db) is None


def test_an_unpriced_step_is_left_out_of_a_money_history(db: Database) -> None:
    for n in range(1, 10):
        _step(db, n, tokens=100, cost=0.1)
    _step(db, 10, tokens=100, cost=None)

    assert _limit(db, "usd") is None
    assert _limit(db) == 100


def test_a_history_that_cost_nothing_gives_no_limit(db: Database) -> None:
    for n in range(1, 11):
        _step(db, n, tokens=0, cost=0.0)

    assert _limit(db) is None
    assert _limit(db, "usd") is None


def test_a_runs_outcomes_are_replaced_whole(db: Database) -> None:
    from specweaver.infrastructure.llm.store import record_step_outcomes

    record_step_outcomes(db, "r1", {"a": "passed", "b": "passed"})
    record_step_outcomes(db, "r1", {"a": "passed"})

    with db.connect() as conn:
        rows = conn.execute("SELECT step_name FROM llm_step_outcome WHERE run_id = 'r1'").fetchall()
    assert [tuple(row) for row in rows] == [("a",)]
