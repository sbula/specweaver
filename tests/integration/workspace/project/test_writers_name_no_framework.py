# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw init` and the archetype inferrer write layer roles under `archetype:`, never a framework.

Proves: TECH-079 FR-10

| Bucket | Case |
|---|---|
| Happy | every `context.yaml` `sw init` writes names a role |
| Boundary | a folder whose code imports FastAPI is still inferred as a role |
| Degradation | not applicable — both writers only write; reading is `framework_for`'s |
| Hostile | not applicable — no input reaches either writer's archetype choice |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from ruamel.yaml import YAML

from specweaver.workflows.planning.models import KNOWN_ARCHETYPES
from specweaver.workspace.analyzers.factory import AnalyzerFactory
from specweaver.workspace.analyzers.inferrer import ContextInferrer
from specweaver.workspace.project.evaluator_schemas import load_evaluator_schemas
from specweaver.workspace.project.scaffold import scaffold_project

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def test_sw_init_writes_roles_only(tmp_path: Path) -> None:
    scaffold_project(tmp_path)
    written = [
        YAML(typ="safe").load(path.read_text(encoding="utf-8")).get("archetype")
        for path in sorted(tmp_path.rglob("context.yaml"))
    ]

    assert written
    assert set(written) <= KNOWN_ARCHETYPES
    assert not set(written) & load_evaluator_schemas().keys()


def test_a_fastapi_folder_is_inferred_as_a_role(tmp_path: Path) -> None:
    folder = tmp_path / "api"
    folder.mkdir()
    (folder / "app.py").write_text("from fastapi import FastAPI\n\napp = FastAPI()\n", "utf-8")

    ContextInferrer(analyzer_factory=AnalyzerFactory).infer_and_write(folder)
    archetype = YAML(typ="safe").load((folder / "context.yaml").read_text("utf-8"))["archetype"]

    assert archetype in KNOWN_ARCHETYPES
