# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The workspace's database code is three parts, each with one reason to change.

Proves: TECH-090 FR-13

| Bucket | Case |
|---|---|
| Happy | `workspace.models` holds the tables, `workspace.lookups` the sync lookups, `workspace.store` the repository |
| Boundary | `workspace.store` defines no table and no lookup, and lists none for export; the two table lists step 1 creates name every table, once |
| Degradation | not applicable: the split has no runtime input that can fail |
| Hostile | `workspace.models` opens nothing: no connection, no session, no file |
"""

from __future__ import annotations

import ast
import importlib
import inspect

import pytest

_TABLES = ("Base", "Project", "ActiveState", "ProjectStandard")
_LOOKUPS = (
    "default_dal_at",
    "project_name_at",
    "domain_profile_at",
    "active_project",
    "project_root_of",
)


@pytest.mark.parametrize("name", _TABLES)
def test_the_tables_live_in_models(name: str) -> None:
    models = importlib.import_module("specweaver.workspace.models")

    assert getattr(models, name).__module__ == "specweaver.workspace.models"


@pytest.mark.parametrize("name", _LOOKUPS)
def test_the_sync_lookups_live_in_lookups(name: str) -> None:
    lookups = importlib.import_module("specweaver.workspace.lookups")

    assert getattr(lookups, name).__module__ == "specweaver.workspace.lookups"


def test_the_store_holds_only_the_repository() -> None:
    store = importlib.import_module("specweaver.workspace.store")

    assert store.WorkspaceRepository.__module__ == "specweaver.workspace.store"
    defined = {
        name
        for name, value in vars(store).items()
        if getattr(value, "__module__", None) == "specweaver.workspace.store"
    }
    assert defined.isdisjoint({*_TABLES, *_LOOKUPS})
    assert not hasattr(store, "__all__")


def test_the_models_open_nothing() -> None:
    models = importlib.import_module("specweaver.workspace.models")
    calls = {
        node.func.attr
        for node in ast.walk(ast.parse(inspect.getsource(models)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not calls & {"connect", "execute", "async_session_scope", "open"}


def test_the_two_table_lists_name_every_table_of_the_shared_metadata() -> None:
    from specweaver.workspace.memory.store import MEMORY_TABLES
    from specweaver.workspace.models import WORKSPACE_TABLES, Base

    listed = [table.name for table in (*WORKSPACE_TABLES, *MEMORY_TABLES)]

    assert sorted(listed) == sorted(Base.metadata.tables)
    assert len(listed) == len(set(listed))
