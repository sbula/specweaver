# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every limit has its place in the machine file, and no number in code.

Proves: C-FLOW-13 FR-17

| Bucket | Case |
|---|---|
| Happy | `[brake]`, a model's and a role's limits parse; `sw config show` lists each with its line |
| Boundary | a file without `[brake]` still parses — the limits are then unset, not defaulted |
| Degradation | not applicable here — refusing a command on an unset limit is proven at the router |
| Hostile | the retired `local_gpu_hours_per_run`, a zero or negative limit, and a limit in a project file are refused |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import (
    LlmSettingsFiles,
    SettingsFileError,
    parse_machine_file,
    parse_project_llm,
    resolve_roles,
    settings_report,
)

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
default = "qwen3-coder-next@gb10"
review = { model = "qwen3-coder-next@gb10", tokens_per_run = 300000 }

[brake]
hosted_spend_per_run = 16
tokens_per_run = 2000000
agent_turns = 30

[models."qwen3-coder-next"]
tokens_per_run = 1000000

[models."claude-sonnet-5"]
spend_per_run = 8
"""


def _report(machine: str = _MACHINE) -> dict[str, tuple[str, str]]:
    files = LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="settings.toml", project_text="", project_source="-"
    )
    return {
        key: (value, origin) for key, value, origin in settings_report(files, resolve_roles(files))
    }


class TestLimitFieldsParse:
    def test_brake_values(self) -> None:
        brake = parse_machine_file(_MACHINE, "settings.toml").brake

        assert (brake.hosted_spend_per_run, brake.tokens_per_run, brake.agent_turns) == (
            16,
            2_000_000,
            30,
        )

    def test_model_limits(self) -> None:
        models = parse_machine_file(_MACHINE, "settings.toml").models

        assert models["qwen3-coder-next"].tokens_per_run == 1_000_000
        assert models["claude-sonnet-5"].spend_per_run == 8

    def test_role_limit(self) -> None:
        roles = parse_machine_file(_MACHINE, "settings.toml").roles

        assert roles["review"].tokens_per_run == 300_000
        assert roles["review"].model == "qwen3-coder-next"

    def test_no_brake_section_means_unset_not_a_default(self) -> None:
        brake = parse_machine_file("", "settings.toml").brake

        assert (brake.hosted_spend_per_run, brake.tokens_per_run, brake.agent_turns) == (
            None,
            None,
            None,
        )


class TestLimitFieldsRefused:
    def test_the_retired_gpu_hours_key(self) -> None:
        with pytest.raises(SettingsFileError, match="local_gpu_hours_per_run"):
            parse_machine_file("[brake]\nlocal_gpu_hours_per_run = 2\n", "settings.toml")

    @pytest.mark.parametrize(
        "line", ["agent_turns = 0", "hosted_spend_per_run = -1", "tokens_per_run = 0"]
    )
    def test_a_limit_that_is_not_positive(self, line: str) -> None:
        with pytest.raises(SettingsFileError, match=r"brake\."):
            parse_machine_file(f"[brake]\n{line}\n", "settings.toml")

    @pytest.mark.parametrize("field", ["spend_per_run", "tokens_per_run"])
    def test_a_limit_in_a_project_file(self, field: str) -> None:
        text = f'[llm.roles]\nreview = {{ model = "qwen3-coder-next@gb10", {field} = 5 }}\n'

        with pytest.raises(SettingsFileError, match="machine settings file") as caught:
            parse_project_llm(text, "specweaver.toml")
        assert caught.value.key == f"llm.roles.review.{field}"
        assert caught.value.line == 2


class TestLimitsInTheReport:
    def test_brake_values_with_their_lines(self) -> None:
        report = _report()

        assert report["brake.hosted_spend_per_run"] == ("16", "settings.toml:12")
        assert report["brake.agent_turns"] == ("30", "settings.toml:14")

    def test_unset_brake_values_say_so(self) -> None:
        report = _report(_MACHINE.split("[brake]")[0])

        value, origin = report["brake.agent_turns"]
        assert value.startswith("unset")
        assert origin == "-"

    def test_model_and_role_limits_are_listed_and_marked_not_yet_applied(self) -> None:
        report = _report()

        assert report["models.qwen3-coder-next.tokens_per_run"] == (
            "1000000 (applied by B-FLOW-05)",
            "settings.toml:17",
        )
        assert report["models.claude-sonnet-5.spend_per_run"][0] == "8 (applied by B-FLOW-05)"
        assert report["roles.review.tokens_per_run"] == (
            "300000 (applied by B-FLOW-05)",
            "settings.toml:9",
        )
