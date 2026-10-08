# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A role that only reads gets read grants; only the implementer may write.

E-SENS-03, done when: an agent's grant is built from its task and refuses everything outside it.

| Bucket | Case |
|---|---|
| Happy | the implementer keeps full access to its roots |
| Boundary | the reviewer and the planner get read access to the same roots |
| Degradation | not applicable — the boundary is built by `WorkspaceBoundary` |
| Hostile | no read-only role holds a write or full grant anywhere |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import AccessMode, WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("role", ["reviewer", "planner"])
def test_a_read_only_role_gets_read_grants_only(tmp_path: Path, role: str) -> None:
    grants = ToolDispatcher._compute_role_grants(role, WorkspaceBoundary(roots=[tmp_path]))

    assert grants
    assert {grant.mode for grant in grants} == {AccessMode.READ}


def test_the_implementer_keeps_full_access(tmp_path: Path) -> None:
    grants = ToolDispatcher._compute_role_grants("implementer", WorkspaceBoundary(roots=[tmp_path]))

    assert {grant.mode for grant in grants} == {AccessMode.FULL}
