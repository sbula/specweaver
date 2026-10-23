# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The constitution size limit is one number, read by the loader and by the stored default.

Proves: TECH-077 FR-10

| Bucket | Case |
|---|---|
| Happy | the loader's default and the database column's default are the one constant |
| Boundary | not applicable — a constant has no range |
| Degradation | not applicable — nothing is read |
| Hostile | not applicable — nothing is input |
"""

from __future__ import annotations

import inspect

from specweaver.commons.limits import DEFAULT_MAX_CONSTITUTION_SIZE
from specweaver.workspace.project.constitution import (
    DEFAULT_MAX_CONSTITUTION_SIZE as LOADER_DEFAULT,
)
from specweaver.workspace.store import Project


def test_the_loader_and_the_store_share_one_limit() -> None:
    column_default = Project.__table__.c.constitution_max_size.default.arg

    assert LOADER_DEFAULT is DEFAULT_MAX_CONSTITUTION_SIZE
    assert column_default == DEFAULT_MAX_CONSTITUTION_SIZE
    assert "5120" not in inspect.getsource(Project)
