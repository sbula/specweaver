# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The LLM settings files parse strictly, and every refusal names its file, key and line.

Proves: C-FLOW-13 FR-4, FR-5

| Bucket | Case |
|---|---|
| Happy | a full machine file and a project section parse into typed models |
| Boundary | empty text; `max_parallel = 0`; a role without `@`; an unknown role name |
| Degradation | empty text means built-in defaults; `schema_version` from the future refuses |
| Hostile | a typo'd key; a wrong type; broken TOML; a project that tries to define a server, a `base_url` or a key variable; a secret-looking value never echoed |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import (
    SettingsFileError,
    parse_machine_file,
    parse_project_llm,
)

_MACHINE = """\
schema_version = 1

[currency]
code = "CHF"
per_usd = 0.80
rate_date = 2026-09-26

[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[servers.anthropic]
kind = "anthropic"
private = false
max_parallel = 3

[roles]
draft = "claude-sonnet@anthropic"
implement = { model = "qwen3-coder-next@gb10", temperature = 1.0 }

[brake]
hosted_spend_per_run = 20
local_gpu_hours_per_run = 2
agent_turns = 10

[models."qwen3-coder-next"]
context = 262144
max_output = 32768
tool_calls = true
usd_per_million_input = 0.0
usd_per_million_output = 0.0
thinking_in_output_cap = true
sampling = { temperature = 1.0, top_p = 0.95, top_k = 40 }
"""


class TestTheMachineFileParses:
    def test_every_section_arrives_typed(self) -> None:
        machine = parse_machine_file(_MACHINE, "settings.toml")

        assert machine.currency is not None and (
            machine.currency.code,
            machine.currency.per_usd,
        ) == ("CHF", 0.80)
        assert machine.servers["gb10"].base_url == "http://gb10:8000/v1"
        assert machine.servers["gb10"].private is True
        assert machine.servers["anthropic"].max_parallel == 3
        assert machine.brake.hosted_spend_per_run == 20
        assert machine.models["qwen3-coder-next"].context == 262144
        assert machine.models["qwen3-coder-next"].usd_per_million_output == 0.0
        assert machine.models["qwen3-coder-next"].thinking_in_output_cap is True

    def test_a_hosted_server_defaults_to_its_providers_key_variable(self) -> None:
        machine = parse_machine_file(_MACHINE, "settings.toml")

        assert machine.servers["anthropic"].api_key_env == "ANTHROPIC_API_KEY"
        assert machine.servers["gb10"].api_key_env is None

    def test_an_explicit_key_variable_is_kept(self) -> None:
        text = _MACHINE.replace(
            'kind = "anthropic"', 'kind = "anthropic"\napi_key_env = "WORK_ANTHROPIC_KEY"'
        )

        assert (
            parse_machine_file(text, "s.toml").servers["anthropic"].api_key_env
            == "WORK_ANTHROPIC_KEY"
        )

    def test_a_role_table_carries_its_sampling(self) -> None:
        role = parse_machine_file(_MACHINE, "s.toml").roles["implement"]

        assert (role.model, role.server, role.temperature) == ("qwen3-coder-next", "gb10", 1.0)

    def test_empty_text_means_the_agreed_defaults(self) -> None:
        machine = parse_machine_file("", "settings.toml")

        assert machine.servers == {}
        assert machine.roles == {}
        assert (machine.brake.hosted_spend_per_run, machine.brake.local_gpu_hours_per_run) == (
            20,
            2,
        )
        assert machine.brake.agent_turns == 10


def _refusal(text: str, *, project: bool = False) -> SettingsFileError:
    parse = parse_project_llm if project else parse_machine_file
    with pytest.raises(SettingsFileError) as caught:
        parse(text, "the-file.toml")
    return caught.value


class TestABrokenMachineFileRefuses:
    def test_a_typo_names_file_key_and_line(self) -> None:
        text = _MACHINE.replace("max_parallel = 4", "max_paralel = 4")

        err = _refusal(text)

        assert err.source == "the-file.toml"
        assert "max_paralel" in err.key
        assert err.line == text.splitlines().index("max_paralel = 4") + 1

    def test_a_wrong_type_names_its_line(self) -> None:
        text = _MACHINE.replace("agent_turns = 10", 'agent_turns = "ten"')

        err = _refusal(text)

        assert "agent_turns" in err.key
        assert err.line == text.splitlines().index('agent_turns = "ten"') + 1

    def test_a_missing_required_key_names_its_table(self) -> None:
        text = _MACHINE.replace("private = false\n", "")

        err = _refusal(text)

        assert "private" in err.key
        assert err.line == text.splitlines().index("[servers.anthropic]") + 1

    def test_broken_toml_names_its_line(self) -> None:
        text = "schema_version = 1\n[servers.gb10\nkind = 'x'\n"

        assert _refusal(text).line == 2

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ("max_parallel = 4", "max_parallel = 0"),
            ('draft = "claude-sonnet@anthropic"', 'draft = "claude-sonnet"'),
            ('draft = "claude-sonnet@anthropic"', 'drafting = "claude-sonnet@anthropic"'),
            ('kind = "anthropic"', 'kind = "anthropik"'),
        ],
    )
    def test_an_invalid_value_refuses(self, old: str, new: str) -> None:
        assert _refusal(_MACHINE.replace(old, new)).line > 0

    def test_a_local_server_without_an_address_refuses(self) -> None:
        text = _MACHINE.replace('base_url = "http://gb10:8000/v1"\n', "")

        err = _refusal(text)

        assert "servers.gb10" in err.key
        assert "base_url" in err.message

    def test_a_qwen_server_without_an_address_refuses(self) -> None:
        text = '[servers.dashscope]\nkind = "qwen"\nprivate = false\nmax_parallel = 2\n'

        err = _refusal(text)

        assert "servers.dashscope" in err.key
        assert "base_url" in err.message

    def test_a_qwen_server_reads_the_dashscope_key_by_default(self) -> None:
        text = (
            '[servers.dashscope]\nkind = "qwen"\nprivate = false\nmax_parallel = 2\n'
            'base_url = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"\n'
        )

        server = parse_machine_file(text, "settings.toml").servers["dashscope"]

        assert server.api_key_env == "DASHSCOPE_API_KEY"

    def test_a_zero_exchange_rate_refuses(self) -> None:
        text = _MACHINE.replace("per_usd = 0.80", "per_usd = 0")

        assert _refusal(text).line == text.splitlines().index("per_usd = 0") + 1

    def test_a_wrong_type_inside_an_inline_role_names_that_line(self) -> None:
        line = 'implement = { model = "qwen3-coder-next@gb10", temperature = "hot" }'
        text = _MACHINE.replace(
            'implement = { model = "qwen3-coder-next@gb10", temperature = 1.0 }', line
        )

        assert _refusal(text).line == text.splitlines().index(line) + 1

    def test_a_wrong_type_under_a_quoted_table_names_its_line(self) -> None:
        text = _MACHINE.replace("context = 262144", 'context = "big"')

        assert _refusal(text).line == text.splitlines().index('context = "big"') + 1

    def test_a_future_schema_version_refuses_with_an_upgrade_message(self) -> None:
        err = _refusal(_MACHINE.replace("schema_version = 1", "schema_version = 99"))

        assert "upgrade" in str(err).lower()

    def test_a_refusal_never_echoes_a_value(self) -> None:
        secret = "sk-live-0123456789abcdef"
        err = _refusal(_MACHINE.replace("max_parallel = 4", f'max_parallel = "{secret}"'))

        assert secret not in str(err)


class TestAProjectMayChooseButNotRedirect:
    def test_a_project_section_parses(self) -> None:
        project = parse_project_llm(
            '[llm]\nprivate_only = true\n[llm.roles]\nimplement = "qwen3-coder-next@gb10"\n',
            "specweaver.toml",
        )

        assert project.private_only is True
        assert project.roles["implement"].model == "qwen3-coder-next"
        assert project.roles["implement"].server == "gb10"

    def test_no_llm_section_is_an_empty_choice(self) -> None:
        project = parse_project_llm("[standards]\nx = 1\n", "specweaver.toml")

        assert project.private_only is False
        assert project.roles == {}

    @pytest.mark.parametrize(
        "text",
        [
            '[llm.servers.evil]\nkind = "openai-compatible"\nbase_url = "http://evil"\n',
            '[llm]\nbase_url = "http://evil"\n',
            '[llm.roles]\nimplement = { model = "m@gb10", base_url = "http://evil" }\n',
            '[llm]\napi_key_env = "HOME"\n',
        ],
    )
    def test_a_project_cannot_say_where_code_is_sent(self, text: str) -> None:
        err = _refusal(text, project=True)

        assert "machine" in str(err).lower()
        assert err.line > 0


def test_a_negative_price_is_refused() -> None:
    text = '[models."m"]\nusd_per_million_input = -1.0\n'

    with pytest.raises(SettingsFileError) as caught:
        parse_machine_file(text, "settings.toml")

    assert caught.value.line == 2


def test_a_currency_code_must_be_three_capital_letters() -> None:
    text = '[currency]\ncode = "chf!"\nper_usd = 0.8\nrate_date = 2026-09-26\n'

    with pytest.raises(SettingsFileError) as caught:
        parse_machine_file(text, "settings.toml")

    assert caught.value.key == "currency.code"
