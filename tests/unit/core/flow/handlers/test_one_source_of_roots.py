# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A boundary has one root, the project's; no field claims a scope that nothing sets.

Proves: E-SENS-03 FR-5

| Bucket | Case |
|---|---|
| Happy | a run's boundary is its project root |
| Boundary | not applicable — there is one root and no list of them |
| Degradation | not applicable — the field is gone, so it cannot be half set |
| Hostile | a run that names `workspace_roots` is refused |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from specweaver.core.flow.handlers.run_context import GraphContext, RunContext
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path


def test_a_runs_boundary_is_its_project_root(tmp_path: Path) -> None:
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "specs" / "a_spec.md")

    assert WorkspaceBoundary.from_run_context(context).roots == [tmp_path]


def test_a_run_that_names_workspace_roots_is_refused() -> None:
    with pytest.raises(ValidationError):
        GraphContext(workspace_roots=["src"])
