# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The protocol tool reads only contracts inside the run's boundary.

Proves: TECH-075 FR-4
Proves: TECH-075 NFR-4

Built the way an agent gets it (`ToolDispatcher.create_standard_set`, `allowed_tools=["protocol"]`)
and called through `execute`. So this proves the registry hands the run's boundary to the tool.

| Bucket | Case |
|---|---|
| Happy | a contract in the project is read |
| Boundary | a contract under a neighbour's read-only API path is read |
| Degradation | a refused path is an error the model sees, never a parsed schema |
| Hostile | `../`, an absolute path, a link that points outside |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

_CONTRACT = "openapi: 3.0.3\npaths:\n  /{name}:\n    get:\n      operationId: {name}\n"


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    project = tmp_path / "proj"
    neighbour = tmp_path / "neighbour_api"
    outside = tmp_path / "outside"
    for folder in (project, neighbour, outside):
        folder.mkdir()
    (project / "api.yaml").write_text(_CONTRACT.format(name="own"), encoding="utf-8")
    (neighbour / "api.yaml").write_text(_CONTRACT.format(name="neighbour"), encoding="utf-8")
    (outside / "api.yaml").write_text(_CONTRACT.format(name="secret"), encoding="utf-8")
    (project / "link.yaml").symlink_to(outside / "api.yaml")
    return {"project": project, "neighbour": neighbour, "outside": outside}


async def _extract(world: dict[str, Path], file_path: str) -> dict[str, Any]:
    boundary = WorkspaceBoundary([world["project"]], api_paths=[world["neighbour"]])
    dispatcher = ToolDispatcher.create_standard_set(
        boundary, role="reviewer", allowed_tools=["protocol"]
    )
    return await dispatcher.execute("extract_schema_endpoints", {"file_path": file_path})


async def test_a_contract_in_the_project_is_read(world: dict[str, Path]) -> None:
    out = await _extract(world, "api.yaml")
    assert "/own" in json.dumps(out)


async def test_a_neighbours_api_contract_is_read(world: dict[str, Path]) -> None:
    out = await _extract(world, str(world["neighbour"] / "api.yaml"))
    assert "/neighbour" in json.dumps(out)


@pytest.mark.parametrize("given", ["../outside/api.yaml", "ABSOLUTE", "link.yaml"])
async def test_a_contract_outside_is_refused(world: dict[str, Path], given: str) -> None:
    file_path = str(world["outside"] / "api.yaml") if given == "ABSOLUTE" else given
    out = await _extract(world, file_path)
    text = json.dumps(out)
    assert "/secret" not in text
    assert "outside the workspace" in text
