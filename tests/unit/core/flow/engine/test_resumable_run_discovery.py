# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`StateStore.get_latest_resumable_run` — the query `sw resume` should have been asking.

Proves: TECH-054 FR-1

Auto-detection used to reconstruct this answer in the CLI, by looping over the 14 bundled pipeline
names and asking `get_latest_run` for each (`flow/interfaces/cli.py:471`). Two things follow from
building it that way, and both were live:

* a run of a pipeline loaded from a **YAML path** — a documented input to `sw run` — appears in no
  such loop, so it could never be auto-resumed;
* "latest" meant *first bundled name with a resumable run*, so a month-old failure could outrank a
  parked run from a minute ago.

The store can answer the question directly, and ordering by `updated_at` is what "latest" meant all
along. Every test below fixes `updated_at` explicitly rather than relying on save order: two runs
saved in the same millisecond would otherwise tie, and the test would pass on row order.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepStatus,
)
from specweaver.core.flow.engine.store import StateStore

if TYPE_CHECKING:
    from pathlib import Path

PROJECT = "demo"


def _save(
    store: StateStore,
    *,
    pipeline: str,
    updated_at: str,
    status: RunStatus,
    project: str = PROJECT,
    run_id: str | None = None,
) -> str:
    run = PipelineRun(
        run_id=run_id or str(uuid.uuid4()),
        parent_run_id=None,
        pipeline_name=pipeline,
        project_name=project,
        spec_path="specs/subject.md",
        status=status,
        current_step=0,
        step_records=[StepRecord(step_name="only", status=StepStatus.PENDING)],
        started_at="2026-08-16T09:00:00Z",
        updated_at=updated_at,
    )
    store.save_run(run)
    return run.run_id


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "pipeline_state.db")


class TestGetLatestResumableRun:
    """The one query, against the four things that used to decide the answer instead."""

    def test_the_most_recently_updated_resumable_run_wins(self, store: StateStore) -> None:
        """[Happy] recency decides — not the order of the bundled-pipeline list.

        `new_feature` sorts ahead of `validate_only` in that list, so it is named first here on
        purpose: under the old loop the stale run won, one line below a docstring promising "the
        newest resumable one".
        """
        _save(
            store,
            pipeline="new_feature",
            updated_at="2026-08-01T09:00:00Z",
            status=RunStatus.FAILED,
        )
        newest = _save(
            store,
            pipeline="validate_only",
            updated_at="2026-08-16T09:00:00Z",
            status=RunStatus.PARKED,
        )

        found = store.get_latest_resumable_run(PROJECT)

        assert found is not None
        assert found.run_id == newest

    def test_a_pipeline_that_is_not_bundled_is_still_found(self, store: StateStore) -> None:
        """[Boundary] the defect itself: `sw run some/pipeline.yaml` is a documented input.

        Its runs were persisted correctly and were unreachable by name, which is why `sw resume
        <run-id>` worked while bare `sw resume` reported nothing to resume.
        """
        run_id = _save(
            store,
            pipeline="a_local_pipeline_from_a_path",
            updated_at="2026-08-16T09:00:00Z",
            status=RunStatus.FAILED,
        )

        found = store.get_latest_resumable_run(PROJECT)

        assert found is not None
        assert found.run_id == run_id

    @pytest.mark.parametrize("status", [RunStatus.PARKED, RunStatus.FAILED])
    def test_both_resumable_statuses_qualify(self, store: StateStore, status: RunStatus) -> None:
        """[Boundary] parked (waiting on a human) and failed (waiting on a fix) both resume."""
        run_id = _save(store, pipeline="p", updated_at="2026-08-16T09:00:00Z", status=status)

        found = store.get_latest_resumable_run(PROJECT)

        assert found is not None
        assert found.run_id == run_id

    def test_a_newer_run_that_is_not_resumable_does_not_shadow_an_older_one(
        self, store: StateStore
    ) -> None:
        """[Boundary] the ordering and the filter must apply together, not one then the other.

        A `SELECT ... ORDER BY updated_at DESC LIMIT 1` that filters afterwards returns the
        completed run and then discards it, reporting nothing to resume while a parked run waits.
        """
        older = _save(
            store, pipeline="p", updated_at="2026-08-10T09:00:00Z", status=RunStatus.PARKED
        )
        _save(store, pipeline="q", updated_at="2026-08-16T09:00:00Z", status=RunStatus.COMPLETED)

        found = store.get_latest_resumable_run(PROJECT)

        assert found is not None
        assert found.run_id == older

    def test_another_project_is_never_offered(self, store: StateStore) -> None:
        """[Hostile] resuming someone else's run would run their scripts against this tree."""
        _save(
            store,
            pipeline="p",
            updated_at="2026-08-16T09:00:00Z",
            status=RunStatus.FAILED,
            project="a-different-project",
        )

        assert store.get_latest_resumable_run(PROJECT) is None

    def test_nothing_resumable_is_none_rather_than_an_error(self, store: StateStore) -> None:
        """[Graceful] having no parked run is the normal case, not a failure.

        The CLI turns this into an exit-0 message; anything raised here would become an exit 1 on
        the day everything is fine.
        """
        _save(store, pipeline="p", updated_at="2026-08-16T09:00:00Z", status=RunStatus.COMPLETED)

        assert store.get_latest_resumable_run(PROJECT) is None

    def test_an_empty_store_is_none(self, store: StateStore) -> None:
        """[Boundary] first use of a fresh project, before any pipeline has run."""
        assert store.get_latest_resumable_run(PROJECT) is None
