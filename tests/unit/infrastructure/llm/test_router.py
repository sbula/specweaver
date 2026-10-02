# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The router is the pipeline's view of the one resolver: a task type in, its role's model out.

Proves: C-FLOW-13 FR-10

| Bucket | Case |
|---|---|
| Happy | a task type gets its role's adapter and settings, exactly as the resolver gives them |
| Boundary | `unknown` asks for the `default` role |
| Degradation | a role nobody set refuses, as the resolver does |
| Hostile | not applicable — task types are a closed enum |
"""

from __future__ import annotations

import json

import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.catalogue import Catalogue
from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.resolve import RoleResolver
from specweaver.infrastructure.llm.router import ModelRouter

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
review = { model = "qwen3-coder-next@gb10", temperature = 0.3 }
default = "qwen3-coder-next@gb10"
"""
_CATALOGUE = Catalogue.from_texts(
    json.dumps({"schema_version": 1, "source": {}, "models": {}}),
    'schema_version = 1\n[models."openai-compatible/qwen3-coder-next"]\nmax_output = 8192\n',
)


def _router(machine: str = _MACHINE) -> ModelRouter:
    files = LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="m", project_text="", project_source="-"
    )
    return ModelRouter(
        RoleResolver(files, telemetry_project="p", budget=SpendBudget(None), catalogue=_CATALOGUE)
    )


def test_a_task_type_gets_its_roles_settings() -> None:
    routed = _router().get_for_task(TaskType.REVIEW)

    assert (routed.config.model, routed.config.temperature) == ("qwen3-coder-next", 0.3)
    assert routed.config.max_output_tokens == 8192


def test_unknown_asks_for_the_default_role() -> None:
    routed = _router().get_for_task(TaskType.UNKNOWN)

    assert routed.config.model == "qwen3-coder-next"
    assert routed.config.temperature is None


def test_a_role_nobody_set_refuses() -> None:
    machine = _MACHINE.replace('default = "qwen3-coder-next@gb10"\n', "")

    with pytest.raises(SettingsFileError):
        _router(machine).get_for_task(TaskType.IMPLEMENT)


def test_every_role_shares_the_resolvers_collectors() -> None:
    router = _router()
    review = router.get_for_task(TaskType.REVIEW)
    draft = router.get_for_task(TaskType.DRAFT)

    assert review.adapter is draft.adapter
    assert router.collectors() == [review.adapter]
