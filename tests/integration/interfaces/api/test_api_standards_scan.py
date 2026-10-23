# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`POST /standards/scan` finds a project's files the way `sw standards scan` does.

Proves: TECH-077 FR-8

A real app and a real project under a dot-folder; the scanner is spied on to see which files it is
given.

| Bucket | Case |
|---|---|
| Happy | a project under `~/.local`-style dot-folder scans its source files |
| Boundary | a file `.specweaverignore` names is left out |
| Degradation | a project with no source files gives no results, not an error |
| Hostile | a dot-folder *inside* the project (`.venv`) is still skipped |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from starlette.testclient import TestClient

from specweaver.assurance.standards.scanner import StandardsScanner
from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture()
def world(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, Path, list[list[str]]]]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    root = tmp_path / ".local" / "proj"
    (root / "src").mkdir(parents=True)
    (root / "src" / "orders.py").write_text("def make_order():\n    return 1\n", encoding="utf-8")
    (root / "src" / "ignored.py").write_text("def skip_me():\n    return 1\n", encoding="utf-8")
    (root / ".specweaverignore").write_text("src/ignored.py\n", encoding="utf-8")
    (root / ".venv").mkdir()
    (root / ".venv" / "lib.py").write_text("def vendored():\n    return 1\n", encoding="utf-8")
    given: list[list[str]] = []
    real = StandardsScanner.scan

    def _spy(self: StandardsScanner, files: list[Path], *args: Any, **kwargs: Any) -> Any:
        given.append(sorted(f.relative_to(root).as_posix() for f in files))
        return real(self, files, *args, **kwargs)

    monkeypatch.setattr(StandardsScanner, "scan", _spy)
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    with TestClient(create_app(token=TEST_TOKEN, db=Database(path)), headers=AUTH) as client:
        client.post(
            "/api/v1/projects", json={"name": "dotted", "path": str(root), "scaffold": False}
        )
        yield client, root, given


def test_a_project_under_a_dot_folder_scans_its_files(world) -> None:
    client, _root, given = world

    answer = client.post("/api/v1/standards/scan", json={"project": "dotted"})

    assert answer.status_code == 200, answer.text
    (files,) = given
    assert "src/orders.py" in files
    assert "src/ignored.py" not in files
    assert ".venv/lib.py" not in files


def test_no_source_files_gives_no_results(world) -> None:
    client, root, _given = world
    for f in (root / "src").iterdir():
        f.unlink()

    answer = client.post("/api/v1/standards/scan", json={"project": "dotted"})

    assert answer.status_code == 200, answer.text
    assert answer.json() == []
