# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A pipeline step's lineage event is written by the one artifact-event repository and read back
by `sw lineage`'s reads, on a real `specweaver.db`.

Proves: TECH-090 FR-14

| Bucket | Case |
|---|---|
| Happy | a step's event reaches the history of its artifact and the children of its parent |
| Boundary | two events of one artifact come back oldest first; every connection is closed |
| Degradation | a file that cannot be opened is logged and the step goes on (never raises) |
| Hostile | an empty artifact id is refused by the repository and logged, nothing written |
"""

from __future__ import annotations

import logging
from contextlib import closing
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.flow.handlers.artifact_lineage import log_artifact_lineage
from specweaver.graph.lineage.store.lineage_repository import LineageRepository
from specweaver.infrastructure.database import Database

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path)


def _context(db: Database) -> SimpleNamespace:
    return SimpleNamespace(db=db, run=SimpleNamespace(run_id="run-7"))


async def test_a_step_event_is_read_back_by_the_lineage_reads(db: Database) -> None:
    await log_artifact_lineage(_context(db), "child", "generated", parent_id="parent", model_id="m")
    await log_artifact_lineage(_context(db), "child", "modified", parent_id="parent", model_id="m")

    repo = LineageRepository(str(db.path))
    history = repo.get_artifact_history("child")
    assert [(e["event_type"], e["run_id"], e["parent_id"]) for e in history] == [
        ("generated", "run-7", "parent"),
        ("modified", "run-7", "parent"),
    ]
    assert [e["artifact_id"] for e in repo.get_children("parent")] == ["child", "child"]


async def test_an_unopenable_file_is_logged_and_the_step_goes_on(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "broken.db"
    path.write_bytes(b"this is not a database " * 100)

    with caplog.at_level(logging.ERROR):
        await log_artifact_lineage(_context(Database(path)), "a", "generated")

    assert "Lineage event 'generated' failed for artifact a" in caplog.text


async def test_an_empty_artifact_id_writes_nothing(
    db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        await log_artifact_lineage(_context(db), " ", "generated")

    assert "artifact_id cannot be empty" in caplog.text
    with closing(db.connect()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM flow_artifact_events").fetchone()[0] == 0


def test_the_repository_closes_every_connection_it_opens(db: Database) -> None:
    import gc
    import warnings

    repo = LineageRepository(db.path)
    gc.collect()  # earlier tests' leftovers are not this repository's
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ResourceWarning)
        repo.log_artifact_event("a", None, "run", "generated", "m")
        repo.get_artifact_history("a")
        repo.get_children("a")
        gc.collect()

    assert [w for w in caught if issubclass(w.category, ResourceWarning)] == []
