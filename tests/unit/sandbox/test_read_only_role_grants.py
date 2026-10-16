# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A role that only reads gets read grants; only the implementer may write, and only its task.

Proves: E-SENS-03 FR-2

| Bucket | Case |
|---|---|
| Happy | the implementer reads its roots and writes only its task's files |
| Boundary | the reviewer and the planner get read access to the same roots |
| Degradation | not applicable — the boundary is built by `WorkspaceBoundary` |
| Hostile | no read-only role holds a write or full grant anywhere |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import AccessMode, FolderGrant, TaskGrant, WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("role", ["reviewer", "planner"])
def test_a_read_only_role_gets_read_grants_only(tmp_path: Path, role: str) -> None:
    grants = ToolDispatcher._compute_role_grants(role, WorkspaceBoundary(roots=[tmp_path]))

    assert grants
    assert {grant.mode for grant in grants} == {AccessMode.READ}


def test_the_implementer_reads_everything_and_writes_its_task_only(tmp_path: Path) -> None:
    grants = ToolDispatcher._compute_role_grants(
        "implementer", WorkspaceBoundary(roots=[tmp_path]), ["src/greeter.py"]
    )

    folders = [grant for grant in grants if isinstance(grant, FolderGrant)]
    tasks = [grant for grant in grants if isinstance(grant, TaskGrant)]
    assert {grant.mode for grant in folders} == {AccessMode.READ}
    assert [task.files for task in tasks] == [("src/greeter.py",)]
