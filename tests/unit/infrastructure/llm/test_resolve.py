# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One resolver gives every role its adapter and generation settings.

Proves: C-FLOW-13 FR-10, FR-11

| Bucket | Case |
|---|---|
| Happy | a role gets its server's adapter and its model; `default` covers a role left unset |
| Boundary | the role's sampling beats the catalogue's; nothing known → nothing sent; the output limit comes from the role, else the catalogue |
| Degradation | no role and no `default`, or a cloud role without its key → refused before any call; an unknown output limit → refused, naming the key |
| Hostile | two roles on one server share one adapter, one parallel limit and one budget |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.catalogue import Catalogue
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.resolve import RoleResolver

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
draft = "qwen3-coder-next@gb10"
review = { model = "qwen3-coder-next@gb10", temperature = 0.3, max_output_tokens = 2048 }
default = "qwen3-coder-next@gb10"
"""

_LOCAL = """\
schema_version = 1

[models."openai-compatible/qwen3-coder-next"]
max_output = 65536
sampling = { temperature = 1.0, top_p = 0.95, top_k = 40 }
"""


def _files(machine: str = _MACHINE) -> LlmSettingsFiles:
    return LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="settings.toml", project_text="", project_source="-"
    )


def _resolver(machine: str = _MACHINE, local: str = _LOCAL) -> RoleResolver:
    return RoleResolver(
        _files(machine),
        telemetry_project="demo",
        budget=SpendBudget(),
        catalogue=Catalogue.from_text(local),
    )


class TestRoleResolverSettings:
    def test_a_role_gets_its_model_and_the_catalogue_sampling(self) -> None:
        _adapter, config = _resolver().for_role("draft")

        assert config.model == "qwen3-coder-next"
        assert (config.temperature, config.top_p, config.top_k) == (1.0, 0.95, 40)
        assert config.max_output_tokens == 65536

    def test_the_role_beats_the_catalogue(self) -> None:
        _adapter, config = _resolver().for_role("review")

        assert config.temperature == 0.3
        assert config.max_output_tokens == 2048

    def test_default_covers_a_role_left_unset(self) -> None:
        _adapter, config = _resolver().for_role("plan")

        assert config.model == "qwen3-coder-next"

    def test_nothing_known_means_no_sampling_is_sent(self) -> None:
        local = _LOCAL.replace("sampling = { temperature = 1.0, top_p = 0.95, top_k = 40 }\n", "")

        _adapter, config = _resolver(local=local).for_role("draft")

        assert (config.temperature, config.top_p, config.top_k) == (None, None, None)


class TestRoleResolverRefuses:
    def test_a_role_with_no_model_and_no_default_is_refused(self) -> None:
        machine = _MACHINE.replace('default = "qwen3-coder-next@gb10"\n', "")

        with pytest.raises(SettingsFileError) as caught:
            _resolver(machine).require(["draft", "implement"])

        assert caught.value.key == "roles.implement"
        assert "roles.default" in caught.value.message

    def test_an_unknown_output_limit_is_refused(self) -> None:
        local = _LOCAL.replace("max_output = 65536\n", "")

        with pytest.raises(SettingsFileError) as caught:
            _resolver(local=local).for_role("draft")

        assert "max_output_tokens" in caught.value.message


class TestRoleResolverKeys:
    def test_a_cloud_role_without_its_key_is_refused_before_any_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("WORK_ANTHROPIC_KEY", raising=False)
        machine = _MACHINE + (
            '\n[servers.work]\nkind = "anthropic"\napi_key_env = "WORK_ANTHROPIC_KEY"\n'
            "private = false\nmax_parallel = 2\n"
        )
        machine = machine.replace(
            'draft = "qwen3-coder-next@gb10"', 'draft = "claude-opus-5-5@work"'
        )

        with pytest.raises(SettingsFileError) as caught:
            _resolver(machine).require(["draft"])

        assert "WORK_ANTHROPIC_KEY" in caught.value.message
        assert caught.value.key == "servers.work.api_key_env"


class TestRoleResolverSharing:
    def test_roles_on_one_server_share_one_adapter_and_one_budget(self) -> None:
        resolver = _resolver()

        draft, _ = resolver.for_role("draft")
        review, _ = resolver.for_role("review")

        assert draft is review
        assert draft.budget is review.budget
        assert resolver.collectors() == [draft]


class TestRoleResolverPrices:
    def test_a_local_model_is_priced_from_the_machine_file_only(self) -> None:
        machine = _MACHINE + '\n[models."qwen3-coder-next"]\nusd_per_million_input = 2.0\n'
        local = _LOCAL.replace(
            "max_output = 65536\n", "max_output = 65536\nusd_per_million_output = 8.0\n"
        )
        adapter, _config = _resolver(machine, local).for_role("draft")

        book = adapter._prices("qwen3-coder-next")

        price_in, price_out = book.default(TokenKind.INPUT), book.default(TokenKind.OUTPUT)
        assert price_in is not None and price_in.usd_per_million == 2.0
        assert price_out is None


class TestTheSearchKey:
    """The web-search key comes from keys.env, through the variable `[search]` names."""

    @staticmethod
    def _with(machine: str, keys: dict[str, str]) -> RoleResolver:
        files = LlmSettingsFiles.from_texts(
            machine_text=machine,
            machine_source="settings.toml",
            project_text="",
            project_source="-",
            keys=keys,
            keys_source="keys.env",
        )
        return RoleResolver(files, telemetry_project="demo", budget=SpendBudget())

    def test_the_named_variable_gives_the_key(self) -> None:
        # Proves: E-SENS-02 FR-4
        machine = _MACHINE + '\n[search]\napi_key_env = "TAVILY_API_KEY"\n'
        resolver = self._with(machine, {"TAVILY_API_KEY": "tvly-1", "OTHER": "x"})
        assert resolver.search_key() == "tvly-1"

    def test_no_section_means_no_key(self) -> None:
        assert self._with(_MACHINE, {"TAVILY_API_KEY": "tvly-1"}).search_key() is None

    def test_a_variable_keys_env_does_not_set_refuses_naming_its_line(self) -> None:
        machine = _MACHINE + '\n[search]\napi_key_env = "TAVILY_API_KEY"\n'
        with pytest.raises(SettingsFileError) as caught:
            self._with(machine, {}).search_key()
        assert caught.value.key == "search.api_key_env"
        assert "TAVILY_API_KEY" in str(caught.value)
        assert caught.value.line == machine.splitlines().index('api_key_env = "TAVILY_API_KEY"') + 1
