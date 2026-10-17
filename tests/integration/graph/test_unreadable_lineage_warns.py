# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A lineage that cannot be read, or a stored DAL that is not a DAL, is a warning.

Proves: D-FLOW-04 FR-8

| Bucket | Case |
|---|---|
| Happy | not applicable — a readable lineage is the engine's own tests |
| Boundary | not applicable — the same fallback as before; only its trace is new |
| Degradation | a lineage store that raises; a project row holding a value that is not a DAL |
| Hostile | the stored DAL is garbage text |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _warned(caplog: pytest.LogCaptureFixture, *words: str) -> bool:
    return any(
        record.levelno == logging.WARNING and all(w in record.getMessage() for w in words)
        for record in caplog.records
    )


class _Disconnected:
    def get_artifact_history(self, _uuid: str) -> Any:
        raise RuntimeError("database is locked")

    def get_children(self, _uuid: str) -> Any:
        raise RuntimeError("database is locked")


def test_an_unreadable_history_leaves_the_root_where_it_is(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from specweaver.graph.lineage.engine import LineageEngine

    assert LineageEngine(_Disconnected()).find_root("a") == "a"
    assert _warned(caplog, "lineage", "database is locked")


def test_an_unreadable_lineage_cuts_the_tree_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from specweaver.graph.lineage.engine import LineageEngine

    LineageEngine(_Disconnected()).build_tree("a")

    assert _warned(caplog, "lineage of a", "database is locked")


def test_a_stored_dal_that_is_not_a_dal_is_ignored_with_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database
    from specweaver.workspace.store import default_dal_at

    bootstrap_database(str(tmp_path / "specweaver.db"))
    db = Database(tmp_path / "specweaver.db")
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO workspace_projects (name, root_path, created_at, last_used_at, log_level,"
            " constitution_max_size, auto_bootstrap_constitution, stitch_mode, default_dal)"
            " VALUES (?, ?, 'x', 'x', 'DEBUG', 1, 'off', 'off', ?)",
            ("greeter", str(tmp_path), "DAL_Z; DROP TABLE x"),
        )

    assert default_dal_at(db, tmp_path) is None
    assert _warned(caplog, "DAL_Z", "ignored")
