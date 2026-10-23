# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A value of the run's registered project, read one way, with one fallback for a failed read.

Proves: TECH-077 FR-10

| Bucket | Case |
|---|---|
| Happy | the value is read for the run's project folder |
| Boundary | a run with no database or no project folder gives None without reading |
| Degradation | a read that raises gives None and a WARNING naming what was read |
| Hostile | not applicable — the reader is the store's, called with the run's own folder |
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from specweaver.core.flow.engine.registered import registered


def test_the_value_is_read_for_the_runs_folder() -> None:
    seen: list[tuple[object, Path]] = []
    context = SimpleNamespace(db="DB", project_path=Path("/p"))

    def read(db: object, root: Path) -> str:
        seen.append((db, root))
        return "value"

    assert registered(context, read, "name") == "value"
    assert seen == [("DB", Path("/p"))]


@pytest.mark.parametrize(("db", "root"), [(None, Path("/p")), ("DB", None)])
def test_nothing_to_read_gives_none(db: object, root: Path | None) -> None:
    def read(_db: object, _root: Path) -> str:
        raise AssertionError("must not be read")

    assert registered(SimpleNamespace(db=db, project_path=root), read, "name") is None


def test_a_failed_read_gives_none_and_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    def read(_db: object, _root: Path) -> str:
        raise OSError("locked")

    with caplog.at_level(logging.WARNING):
        value = registered(SimpleNamespace(db="DB", project_path=Path("/p")), read, "default DAL")

    assert value is None
    assert any("default DAL" in r.getMessage() for r in caplog.records)
