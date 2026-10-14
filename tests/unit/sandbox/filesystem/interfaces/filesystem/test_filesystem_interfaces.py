# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The filesystem interface a model gets: read, list, search — the same for every role.

A method the interface does not have cannot be called, so no role can write through it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.filesystem.interfaces.facades import (
    FileReadInterface,
    create_filesystem_interface,
)
from specweaver.sandbox.security import AccessMode, FolderGrant

if TYPE_CHECKING:
    from pathlib import Path

_ROLES = ["implementer", "reviewer", "planner", "drafter", "scenario_agent", "arbiter_agent"]
_READ_METHODS = {"read_file", "list_directory", "grep", "find_files"}
_WRITE_METHODS = {"write_file", "edit_file", "create_file", "delete_file"}
_GRANTS = [
    FolderGrant("src", AccessMode.FULL, recursive=True),
    FolderGrant("specs", AccessMode.READ, recursive=True),
]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "src" / "domain" / "billing").mkdir(parents=True)
    (tmp_path / "src" / "domain" / "billing" / "calc.py").write_text(
        "def total(a, b): return a + b", encoding="utf-8"
    )
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "billing.md").write_text("# Billing\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("role", _ROLES)
def test_every_role_gets_the_read_methods_and_no_write(project: Path, role: str) -> None:
    iface = create_filesystem_interface(role, project, _GRANTS)

    assert isinstance(iface, FileReadInterface)
    for method in _READ_METHODS:
        assert callable(getattr(iface, method)), method
    for method in _WRITE_METHODS:
        assert not hasattr(iface, method), method


@pytest.mark.parametrize("role", _ROLES)
def test_every_role_reads_lists_and_searches(project: Path, role: str) -> None:
    iface = create_filesystem_interface(role, project, _GRANTS)

    assert iface.read_file("src/domain/billing/calc.py").status == "success"
    assert "src/domain/billing/calc.py" in iface.list_directory("src/domain/billing").data
    assert iface.grep(pattern="def", path="src/domain/billing").status == "success"
    assert iface.find_files(pattern="*.md", path="specs").status == "success"


def test_a_read_outside_the_grants_is_refused(project: Path) -> None:
    iface = create_filesystem_interface(
        "reviewer", project, [FolderGrant("specs", AccessMode.READ, recursive=True)]
    )
    assert iface.read_file("src/domain/billing/calc.py").status == "error"


def test_the_interface_reports_its_role(project: Path) -> None:
    assert create_filesystem_interface("planner", project, _GRANTS).role == "planner"


def test_an_unknown_role_is_refused(project: Path) -> None:
    with pytest.raises(ValueError, match="Unknown role"):
        create_filesystem_interface("hacker", project, [])
