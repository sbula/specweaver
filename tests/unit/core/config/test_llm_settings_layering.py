# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One resolved setting per role, and each value says where it came from.

Proves: C-FLOW-13 FR-3

| Bucket | Case |
|---|---|
| Happy | machine role alone; project beats machine; a run override beats both |
| Boundary | a role table overrides one sampling value and inherits the rest as unset; no files at all |
| Degradation | a role naming a server nobody defined refuses, naming the role and its line |
| Hostile | a project choosing a server the machine file does not define is refused, not trusted |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import (
    RUN_OVERRIDE,
    LlmSettingsFiles,
    RoleEntry,
    SettingsFileError,
    resolve_roles,
    settings_report,
)

_MACHINE = """\
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
implement = "claude-opus@anthropic"
"""

_PROJECT = """\
[llm.roles]
implement = { model = "qwen3-coder-next@gb10", temperature = 1.0 }
"""


def _line(text: str, content: str) -> int:
    return text.splitlines().index(content) + 1


def _files(machine: str = _MACHINE, project: str = _PROJECT) -> LlmSettingsFiles:
    return LlmSettingsFiles.from_texts(
        machine_text=machine,
        machine_source="machine.toml",
        project_text=project,
        project_source="project.toml",
    )


class TestLayering:
    def test_a_machine_role_stands_alone(self) -> None:
        draft = resolve_roles(_files())["draft"]

        assert (draft.model, draft.server) == ("claude-sonnet", "anthropic")
        line = _line(_MACHINE, 'draft = "claude-sonnet@anthropic"')
        assert draft.origin["model"] == f"machine.toml:{line}"

    def test_the_project_beats_the_machine(self) -> None:
        implement = resolve_roles(_files())["implement"]

        assert (implement.model, implement.server, implement.temperature) == (
            "qwen3-coder-next",
            "gb10",
            1.0,
        )
        assert implement.origin["model"] == "project.toml:2"
        assert implement.origin["temperature"] == "project.toml:2"

    def test_a_run_override_beats_both(self) -> None:
        override = {"implement": RoleEntry.model_validate("claude-opus@anthropic")}

        implement = resolve_roles(_files(), run_overrides=override)["implement"]

        assert (implement.model, implement.server) == ("claude-opus", "anthropic")
        assert implement.origin["model"] == "run --model"

    def test_an_unset_sampling_value_stays_unset(self) -> None:
        implement = resolve_roles(_files())["implement"]

        assert implement.top_p is None
        assert "top_p" not in implement.origin

    def test_no_files_means_no_roles(self) -> None:
        assert resolve_roles(_files(machine="", project="")) == {}


class TestAServerMustExist:
    def test_a_machine_role_naming_an_unknown_server_refuses(self) -> None:
        machine = _MACHINE.replace("claude-sonnet@anthropic", "claude-sonnet@nowhere")

        with pytest.raises(SettingsFileError) as caught:
            resolve_roles(_files(machine=machine, project=""))

        assert caught.value.key == "roles.draft"
        assert caught.value.line == _line(machine, 'draft = "claude-sonnet@nowhere"')
        assert "nowhere" in caught.value.message

    def test_a_project_cannot_invent_a_server(self) -> None:
        project = '[llm.roles]\nimplement = "qwen@my-own-box"\n'

        with pytest.raises(SettingsFileError) as caught:
            resolve_roles(_files(project=project))

        assert caught.value.source == "project.toml"
        assert caught.value.key == "llm.roles.implement"
        assert caught.value.line == 2

    def test_a_run_override_naming_an_unknown_server_refuses(self) -> None:
        override = {"draft": RoleEntry.model_validate("m@nowhere")}

        with pytest.raises(SettingsFileError) as caught:
            resolve_roles(_files(), run_overrides=override)

        assert caught.value.source == RUN_OVERRIDE


class TestTheReport:
    def _rows(self, machine: str, project: str = "") -> dict[str, tuple[str, str]]:
        files = _files(machine=machine, project=project)
        return {
            key: (value, origin)
            for key, value, origin in settings_report(files, resolve_roles(files))
        }

    def test_a_server_shows_its_key_variable_never_a_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret-value-123")

        value, origin = self._rows(_MACHINE)["servers.anthropic"]

        assert "key=ANTHROPIC_API_KEY" in value
        assert "sk-ant-secret-value-123" not in value
        assert origin == f"machine.toml:{_line(_MACHINE, '[servers.anthropic]')}"

    def test_a_set_currency_and_a_private_project_name_their_lines(self) -> None:
        machine = _MACHINE + "\n[currency]\nusd_to_chf = 0.8\nrate_date = 2026-09-26\n"
        project = "[llm]\nprivate_only = true\n"

        rows = self._rows(machine, project)

        assert rows["currency"][0] == "0.8 CHF per USD, dated 2026-09-26"
        assert rows["currency"][1] == f"machine.toml:{_line(machine, '[currency]')}"
        assert rows["llm.private_only"] == ("true", "project.toml:2")
