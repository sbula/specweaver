# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`--model` gives every role of one run the same model; the files stay as they are.

Proves: C-FLOW-13 FR-16

| Bucket | Case |
|---|---|
| Happy | a role set in the machine or project file, a role left to `default`, and `default` itself all get the run model |
| Boundary | the run model replaces a role's model and sampling |
| Degradation | no run model → the files decide, as before |
| Hostile | a run model on a server the file does not define, or on a hosted server in a private-only project → refused before any call |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, RoleEntry, SettingsFileError
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.catalogue import Catalogue
from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.resolve import RoleResolver
from specweaver.infrastructure.llm.router import build_router

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[servers.spare]
kind = "openai-compatible"
base_url = "http://spare:8000/v1"
private = true
max_parallel = 2

[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[roles]
review = { model = "qwen3-coder-next@gb10", temperature = 0.3 }
default = "qwen3-coder-next@gb10"

[brake]
hosted_spend_per_run = 1000
tokens_per_run = 100000000
agent_turns = 10
"""

_CATALOGUE = Catalogue.from_text(
    """\
schema_version = 1

[models."openai-compatible/qwen3-coder-next"]
max_output = 65536
sampling = { temperature = 1.0 }

[models."openai-compatible/spare-coder"]
max_output = 8192
""",
)


def _files(project: str = "") -> LlmSettingsFiles:
    return LlmSettingsFiles.from_texts(
        machine_text=_MACHINE,
        machine_source="settings.toml",
        project_text=project,
        project_source="specweaver.toml",
    )


def _resolver(run_model: str | None, project: str = "") -> RoleResolver:
    return RoleResolver(
        _files(project),
        telemetry_project="demo",
        budget=SpendBudget(),
        catalogue=_CATALOGUE,
        run_model=RoleEntry.model_validate(run_model) if run_model else None,
    )


class TestRunModelReplacesEveryRole:
    @pytest.mark.parametrize("role", ["review", "plan", "default"])
    def test_every_role_gets_the_run_model(self, role: str) -> None:
        resolver = _resolver("spare-coder@spare")

        _adapter, config = resolver.for_role(role)

        assert config.model == "spare-coder"
        assert config.max_output_tokens == 8192  # the run model's own facts, not the file model's

    def test_the_files_sampling_for_a_role_is_not_kept(self) -> None:
        _adapter, config = _resolver("qwen3-coder-next@spare").for_role("review")

        assert config.temperature == 1.0  # the catalogue's, not the file's 0.3

    def test_a_role_the_project_file_sets_gets_the_run_model_too(self) -> None:
        project = '[llm.roles]\nplan = "qwen3-coder-next@gb10"\n'

        _adapter, config = _resolver("spare-coder@spare", project=project).for_role("plan")

        assert config.model == "spare-coder"

    def test_every_role_goes_to_the_run_models_server(self) -> None:
        resolver = _resolver("spare-coder@spare")

        adapters = {id(resolver.for_role(role)[0]) for role in ("review", "plan", "draft")}
        assert len(adapters) == 1
        assert {c._adapter._key for c in resolver.collectors()} == {"spare"}


class TestWithoutRunModel:
    def test_the_files_decide(self) -> None:
        _adapter, config = _resolver(None).for_role("review")

        assert (config.model, config.temperature) == ("qwen3-coder-next", 0.3)


class TestRunModelRefused:
    def test_a_server_the_file_does_not_define(self) -> None:
        with pytest.raises(SettingsFileError, match="nowhere"):
            _resolver("spare-coder@nowhere")

    def test_a_hosted_server_in_a_private_only_project(self) -> None:
        with pytest.raises(SettingsFileError, match="private servers only"):
            _resolver("qwen3-coder-next@hosted", project="[llm]\nprivate_only = true\n")


class TestBuildRouterPassesTheRunModel:
    def test_the_router_resolves_every_task_to_the_run_model(self) -> None:
        router = build_router(
            _files(),
            project="demo",
            roles=[TaskType.REVIEW, TaskType.IMPLEMENT],
            run_model=RoleEntry.model_validate("qwen3-coder-next@spare"),
        )

        assert router.get_for_task(TaskType.REVIEW).config.temperature == 1.0
        assert {c._adapter._key for c in router.collectors()} == {"spare"}
