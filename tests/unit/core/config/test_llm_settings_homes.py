# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The LLM settings have three homes: the schema, the parsing, and role resolution with its report.

Proves: TECH-076 FR-9

| Bucket | Case |
|---|---|
| Happy | text parsed in the parsing home resolves roles in the roles home, with models from the schema |
| Boundary | an empty project section resolves the machine roles alone |
| Degradation | a role naming an unknown server is refused by role resolution, naming its line |
| Hostile | the schema module carries no parser and no resolver |
"""

from __future__ import annotations

import pytest

from specweaver.core.config import llm_settings
from specweaver.core.config.llm_roles import resolve_roles
from specweaver.core.config.llm_settings import RoleEntry
from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.core.config.settings_file import SettingsFileError

_MACHINE = """schema_version = 1

[servers.local]
kind = "openai-compatible"
base_url = "http://127.0.0.1:8080/v1"
private = true
max_parallel = 1

[roles]
review = "qwen@local"
"""


def _files(machine: str, project: str = "") -> LlmSettingsFiles:
    return LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="m.toml", project_text=project, project_source="p.toml"
    )


def test_parsed_text_resolves_roles_with_schema_models() -> None:
    resolved = resolve_roles(_files(_MACHINE), {"draft": RoleEntry.model_validate("qwen@local")})

    assert (resolved["review"].model, resolved["draft"].model) == ("qwen", "qwen")


def test_an_empty_project_section_resolves_the_machine_roles() -> None:
    assert list(resolve_roles(_files(_MACHINE))) == ["review"]


def test_an_unknown_server_is_refused_naming_its_line() -> None:
    with pytest.raises(SettingsFileError) as caught:
        resolve_roles(_files(_MACHINE.replace("qwen@local", "qwen@nowhere")))

    assert (caught.value.key, caught.value.line) == ("roles.review", 10)


def test_the_schema_module_holds_no_parser_or_resolver() -> None:
    for name in ("parse_machine_file", "parse_project_llm", "LlmSettingsFiles", "resolve_roles"):
        assert not hasattr(llm_settings, name), name
