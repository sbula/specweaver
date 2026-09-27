# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each model's facts come from one catalogue, layered generated → local → machine file.

Proves: C-FLOW-13 FR-6

| Bucket | Case |
|---|---|
| Happy | a hosted model has its prices, context and output limit from the generated file |
| Boundary | local beats generated, the machine file beats both, field by field; a kind's default applies until a model sets its own |
| Degradation | an unknown model has no facts, not zeros; an unknown schema version refuses |
| Hostile | a model on a local server never borrows a hosted namesake's price; an unknown field refuses |
"""

from __future__ import annotations

import json

import pytest

from specweaver.core.config.llm_settings import ModelFacts, SettingsFileError
from specweaver.infrastructure.llm.catalogue import Catalogue


def _generated(**models: dict) -> str:
    return json.dumps(
        {
            "schema_version": 1,
            "source": {"url": "https://models.dev/api.json"},
            "models": models
            or {
                "anthropic/claude-sonnet-4-5": {
                    "context": 1000000,
                    "max_output": 64000,
                    "tool_calls": True,
                    "usd_per_million_input": 3.0,
                    "usd_per_million_output": 15.0,
                },
                "qwen/qwen3-coder-next": {
                    "context": 262144,
                    "usd_per_million_input": 0.5,
                    "usd_per_million_output": 2.0,
                },
            },
        }
    )


_LOCAL = """\
schema_version = 1

[kinds.anthropic]
thinking_in_output_cap = true

[models."anthropic/claude-sonnet-4-5"]
max_output = 32000

[models."openai-compatible/qwen3-coder-next"]
context = 262144
tool_calls = true
note = "vLLM: --tool-call-parser qwen3_xml"
"""


def _catalogue(generated: str | None = None, local: str = _LOCAL) -> Catalogue:
    return Catalogue.from_texts(generated or _generated(), local)


class TestCatalogueFacts:
    def test_a_hosted_model_has_its_generated_facts(self) -> None:
        facts = _catalogue().facts("anthropic", "claude-sonnet-4-5", {})

        assert facts is not None
        assert (facts.usd_per_million_input, facts.usd_per_million_output) == (3.0, 15.0)
        assert facts.context == 1000000

    def test_local_beats_generated_one_field_at_a_time(self) -> None:
        facts = _catalogue().facts("anthropic", "claude-sonnet-4-5", {})

        assert facts is not None
        assert facts.max_output == 32000
        assert facts.tool_calls is True

    def test_the_machine_file_beats_both(self) -> None:
        overrides = {"claude-sonnet-4-5": ModelFacts(usd_per_million_input=1.0)}

        facts = _catalogue().facts("anthropic", "claude-sonnet-4-5", overrides)

        assert facts is not None
        assert facts.usd_per_million_input == 1.0
        assert facts.usd_per_million_output == 15.0

    def test_a_kind_default_applies_until_the_model_sets_its_own(self) -> None:
        catalogue = _catalogue()
        inherited = catalogue.facts("anthropic", "claude-sonnet-4-5", {})
        overrides = {"claude-sonnet-4-5": ModelFacts(thinking_in_output_cap=False)}
        own = catalogue.facts("anthropic", "claude-sonnet-4-5", overrides)

        assert inherited is not None and inherited.thinking_in_output_cap is True
        assert own is not None and own.thinking_in_output_cap is False

    def test_a_machine_sampling_table_replaces_the_shipped_one_whole(self) -> None:
        local = _LOCAL + "sampling = { temperature = 0.7, top_k = 20 }\n"
        overrides = {"qwen3-coder-next": ModelFacts.model_validate({"sampling": {"top_p": 0.9}})}

        facts = _catalogue(local=local).facts("openai-compatible", "qwen3-coder-next", overrides)

        assert facts is not None and facts.sampling is not None
        assert (facts.sampling.top_p, facts.sampling.top_k) == (0.9, None)

    def test_an_unknown_model_has_no_facts(self) -> None:
        assert _catalogue().facts("anthropic", "claude-nonexistent", {}) is None

    def test_a_machine_entry_alone_is_enough(self) -> None:
        overrides = {"my-finetune": ModelFacts(context=8192)}

        facts = _catalogue().facts("openai-compatible", "my-finetune", overrides)

        assert facts is not None and facts.context == 8192

    def test_a_local_server_never_borrows_a_hosted_price(self) -> None:
        facts = _catalogue().facts("openai-compatible", "qwen3-coder-next", {})

        assert facts is not None
        assert facts.context == 262144
        assert facts.usd_per_million_input is None

    def test_a_local_server_with_only_a_hosted_namesake_has_no_facts(self) -> None:
        assert _catalogue().facts("openai-compatible", "claude-sonnet-4-5", {}) is None


class TestCatalogueFromTexts:
    def test_an_unknown_generated_schema_version_refuses(self) -> None:
        generated = json.loads(_generated())
        generated["schema_version"] = 99

        with pytest.raises(SettingsFileError) as caught:
            Catalogue.from_texts(json.dumps(generated), _LOCAL)

        assert "update" in caught.value.message

    def test_an_unknown_local_schema_version_refuses(self) -> None:
        with pytest.raises(SettingsFileError):
            Catalogue.from_texts(
                _generated(), _LOCAL.replace("schema_version = 1", "schema_version = 2")
            )

    def test_an_unknown_field_in_a_model_refuses(self) -> None:
        generated = _generated(**{"openai/gpt-x": {"contxt": 5}})

        with pytest.raises(SettingsFileError) as caught:
            Catalogue.from_texts(generated, _LOCAL)

        assert caught.value.key == "openai/gpt-x.contxt"
