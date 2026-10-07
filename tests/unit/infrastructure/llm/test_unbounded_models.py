# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the brake cannot bound is refused before the first call; every routed call names its role.

Proves: B-FLOW-05 FR-5, B-FLOW-05 FR-9

| Bucket | Case |
|---|---|
| Happy | a hosted model with prices and a thinking cap, and any model on a private server, are accepted |
| Boundary | the router stamps each config with its task, so the role's limit applies on every path |
| Degradation | a hosted model whose thinking cap is unknown is refused, naming the key |
| Hostile | a hosted model with no price, and a role limit in the wrong unit for its server, are refused |
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

_SERVERS = """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2
"""

_PRICED = """
[models."priced"]
max_output = 1000
usd_per_million_input = 1.0
usd_per_million_output = 2.0
thinking_in_output_cap = true
"""

_CATALOGUE = Catalogue.from_texts(
    json.dumps({"schema_version": 1, "source": {}, "models": {}}), "schema_version = 1\n"
)


def _resolver(roles: str, models: str = _PRICED) -> RoleResolver:
    files = LlmSettingsFiles.from_texts(
        machine_text=_SERVERS + "\n[roles]\n" + roles + models,
        machine_source="settings.toml",
        project_text="",
        project_source="-",
    )
    return RoleResolver(files, telemetry_project="p", budget=SpendBudget(), catalogue=_CATALOGUE)


class TestAccepted:
    def test_a_priced_capped_hosted_model(self) -> None:
        _resolver('review = "priced@hosted"\n').require(["review"])

    def test_any_model_on_a_private_server(self) -> None:
        _resolver('review = { model = "free@gb10", max_output_tokens = 100 }\n').require(["review"])


class TestRefused:
    def test_a_hosted_model_with_no_price(self) -> None:
        models = '\n[models."unpriced"]\nmax_output = 100\nthinking_in_output_cap = true\n'

        with pytest.raises(SettingsFileError) as caught:
            _resolver('review = "unpriced@hosted"\n', models).require(["review"])

        assert caught.value.key == 'models."unpriced".usd_per_million_input'

    def test_a_hosted_model_whose_thinking_cap_is_unknown(self) -> None:
        models = _PRICED.replace("thinking_in_output_cap = true\n", "")

        with pytest.raises(SettingsFileError) as caught:
            _resolver('review = "priced@hosted"\n', models).require(["review"])

        assert caught.value.key == 'models."priced".thinking_in_output_cap'

    @pytest.mark.parametrize(
        ("role", "key"),
        [
            (
                'review = { model = "free@gb10", max_output_tokens = 100, spend_per_run = 5 }',
                "spend_per_run",
            ),
            ('review = { model = "priced@hosted", tokens_per_run = 500 }', "tokens_per_run"),
        ],
    )
    def test_a_role_limit_in_the_wrong_unit_for_its_server(self, role: str, key: str) -> None:
        with pytest.raises(SettingsFileError) as caught:
            _resolver(role + "\n").require(["review"])

        assert caught.value.key == f"roles.review.{key}"

    def test_the_refusal_also_holds_for_a_role_resolved_later(self) -> None:
        models = '\n[models."unpriced"]\nmax_output = 100\nthinking_in_output_cap = true\n'

        with pytest.raises(SettingsFileError):
            _resolver('default = "unpriced@hosted"\n', models).for_role("plan")


class TestRouterStampsTheTask:
    @pytest.mark.parametrize("task", [TaskType.REVIEW, TaskType.IMPLEMENT])
    def test_each_routed_config_carries_its_task(self, task: TaskType) -> None:
        router = ModelRouter(_resolver('default = "priced@hosted"\n'))

        assert router.get_for_task(task).config.task_type is task
