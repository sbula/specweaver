# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each model's facts come from one shipped list, corrected by the machine file.

Proves: C-FLOW-13 FR-6, NFR-5

| Bucket | Case |
|---|---|
| Happy | a hosted model has its prices, context and output limit from the shipped list |
| Boundary | the machine file beats the list, field by field; a kind's default applies until a model sets its own |
| Degradation | an unknown model has no facts, not zeros; an unknown schema version refuses |
| Hostile | a model on a local server never borrows a hosted namesake's price; an unknown field refuses |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.infrastructure.llm.catalogue import Catalogue

_LIST = """\
schema_version = 1
checked = "2026-10-08"

[kinds.anthropic]
thinking_in_output_cap = true

[models."anthropic/claude-sonnet-4-5"]
context = 1000000
max_output = 32000
tool_calls = true
usd_per_million_input = 3.0
usd_per_million_output = 15.0

[models."qwen/qwen3-coder-next"]
context = 262144
usd_per_million_input = 0.5
usd_per_million_output = 2.0

[models."openai-compatible/qwen3-coder-next"]
context = 262144
tool_calls = true
note = "vLLM: --tool-call-parser qwen3_xml"
"""


def _catalogue(text: str = _LIST) -> Catalogue:
    return Catalogue.from_text(text)


class TestCatalogueFacts:
    def test_a_hosted_model_has_its_listed_facts(self) -> None:
        facts = _catalogue().facts("anthropic", "claude-sonnet-4-5", {})

        assert facts is not None
        assert (facts.usd_per_million_input, facts.usd_per_million_output) == (3.0, 15.0)
        assert facts.context == 1000000

    def test_the_machine_file_beats_the_list(self) -> None:
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
        listed = _LIST + "sampling = { temperature = 0.7, top_k = 20 }\n"
        overrides = {"qwen3-coder-next": ModelFacts.model_validate({"sampling": {"top_p": 0.9}})}

        facts = _catalogue(listed).facts("openai-compatible", "qwen3-coder-next", overrides)

        assert facts is not None and facts.sampling is not None
        assert (facts.sampling.top_p, facts.sampling.top_k) == (0.9, None)

    def test_a_kind_qualified_entry_applies_to_that_kind_only(self) -> None:
        overrides = {"anthropic/claude-sonnet-4-5": ModelFacts(usd_per_million_input=1.0)}
        catalogue = _catalogue()

        hosted = catalogue.facts("anthropic", "claude-sonnet-4-5", overrides)
        local = catalogue.facts("openai-compatible", "claude-sonnet-4-5", overrides)

        assert hosted is not None and hosted.usd_per_million_input == 1.0
        assert local is None

    def test_a_kind_qualified_entry_beats_a_bare_one(self) -> None:
        overrides = {
            "claude-sonnet-4-5": ModelFacts(usd_per_million_input=2.0),
            "anthropic/claude-sonnet-4-5": ModelFacts(usd_per_million_input=1.0),
        }

        facts = _catalogue().facts("anthropic", "claude-sonnet-4-5", overrides)

        assert facts is not None and facts.usd_per_million_input == 1.0

    def test_a_model_id_with_a_slash_still_matches_bare(self) -> None:
        overrides = {"openai/gpt-5": ModelFacts(context=4096)}

        facts = _catalogue().facts("openai-compatible", "openai/gpt-5", overrides)

        assert facts is not None and facts.context == 4096

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


class TestCatalogueFromText:
    def test_the_check_date_is_kept(self) -> None:
        assert _catalogue().checked == "2026-10-08"

    def test_an_unknown_schema_version_refuses(self) -> None:
        with pytest.raises(SettingsFileError) as caught:
            Catalogue.from_text(_LIST.replace("schema_version = 1", "schema_version = 99"))

        assert "update" in caught.value.message

    def test_an_unknown_field_in_a_model_refuses(self) -> None:
        with pytest.raises(SettingsFileError) as caught:
            Catalogue.from_text(_LIST + '\n[models."openai/gpt-x"]\ncontxt = 5\n')

        assert caught.value.key == "openai/gpt-x.contxt"
