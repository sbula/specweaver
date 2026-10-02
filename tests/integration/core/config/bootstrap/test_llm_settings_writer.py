# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Commands write the machine settings file, and leave everything else in it as it was.

Proves: C-FLOW-13 FR-15, NFR-6

| Bucket | Case |
|---|---|
| Happy | setting a model's price with no file → the file exists and parses to that price |
| Boundary | a file with comments and other keys → those survive, byte for byte, in order |
| Degradation | clearing a price nobody set → nothing written |
| Hostile | a negative price or a dotted model name → refused / quoted; the file is never left broken |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.llm_settings_writer import (
    clear_model_price,
    set_model_price,
    set_role,
)
from specweaver.core.config.llm_settings import (
    SettingsFileError,
    parse_machine_file,
    parse_project_llm,
)

if TYPE_CHECKING:
    from pathlib import Path

_EXISTING = """\
# my GB10 setup — keep this comment
[servers.gb10]
kind = "openai-compatible"   # vLLM
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[models."qwen3-coder-next"]
max_output = 16384   # fits --max-model-len
"""


@pytest.fixture()
def machine_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    return tmp_path / "settings.toml"


def test_a_price_set_without_a_file_creates_it(machine_file: Path) -> None:
    set_model_price("claude-opus-5-5", 4.0, 20.0)

    facts = parse_machine_file(machine_file.read_text(encoding="utf-8"), "x").models[
        "claude-opus-5-5"
    ]
    assert (facts.usd_per_million_input, facts.usd_per_million_output) == (4.0, 20.0)


def test_everything_else_in_the_file_survives(machine_file: Path) -> None:
    machine_file.write_text(_EXISTING, encoding="utf-8")

    set_model_price("qwen3-coder-next", 0.0, 0.0)

    text = machine_file.read_text(encoding="utf-8")
    assert text.startswith(_EXISTING.rstrip("\n"))
    facts = parse_machine_file(text, "x").models["qwen3-coder-next"]
    assert (facts.max_output, facts.usd_per_million_input) == (16384, 0.0)


def test_clearing_a_price_leaves_the_other_facts(machine_file: Path) -> None:
    machine_file.write_text(_EXISTING, encoding="utf-8")
    set_model_price("qwen3-coder-next", 1.0, 2.0)

    assert clear_model_price("qwen3-coder-next") is True

    assert machine_file.read_text(encoding="utf-8") == _EXISTING


def test_clearing_a_price_nobody_set_writes_nothing(machine_file: Path) -> None:
    machine_file.write_text(_EXISTING, encoding="utf-8")

    assert clear_model_price("claude-opus-5-5") is False
    assert machine_file.read_text(encoding="utf-8") == _EXISTING


def test_a_negative_price_is_refused_and_the_file_is_untouched(machine_file: Path) -> None:
    machine_file.write_text(_EXISTING, encoding="utf-8")

    with pytest.raises(SettingsFileError):
        set_model_price("qwen3-coder-next", -1.0, 2.0)

    assert machine_file.read_text(encoding="utf-8") == _EXISTING


def test_a_dotted_model_name_stays_one_key(machine_file: Path) -> None:
    set_model_price("qwen3.8-max", 1.5, 4.5)

    models = parse_machine_file(machine_file.read_text(encoding="utf-8"), "x").models
    assert list(models) == ["qwen3.8-max"]


class TestSetRole:
    """`sw config set-role` writes a role into the machine file or the project's `[llm.roles]`."""

    def test_a_machine_role_is_written_and_comments_survive(self, machine_file: Path) -> None:
        machine_file.write_text(_EXISTING, encoding="utf-8")

        set_role("draft", "qwen3-coder-next@gb10")

        text = machine_file.read_text(encoding="utf-8")
        assert text.startswith(_EXISTING.rstrip("\n"))
        assert parse_machine_file(text, "x").roles["draft"].model == "qwen3-coder-next"

    def test_a_project_role_goes_into_the_projects_llm_section(
        self, machine_file: Path, tmp_path: Path
    ) -> None:
        machine_file.write_text(_EXISTING, encoding="utf-8")
        project = tmp_path / "proj"
        project.mkdir()
        (project / "specweaver.toml").write_text(
            '[sandbox]\nexecution_mode = "host"\n', encoding="utf-8"
        )

        set_role("review", "qwen3-coder-next@gb10", project_root=project)

        text = (project / "specweaver.toml").read_text(encoding="utf-8")
        assert text.startswith('[sandbox]\nexecution_mode = "host"\n')
        assert parse_project_llm(text, "x").roles["review"].server == "gb10"

    def test_a_role_on_an_unknown_server_is_refused_and_nothing_written(
        self, machine_file: Path
    ) -> None:
        machine_file.write_text(_EXISTING, encoding="utf-8")

        with pytest.raises(SettingsFileError) as caught:
            set_role("draft", "claude-opus-5-5@nowhere")

        assert "nowhere" in caught.value.message
        assert machine_file.read_text(encoding="utf-8") == _EXISTING

    def test_a_private_project_refuses_a_hosted_role(
        self, machine_file: Path, tmp_path: Path
    ) -> None:
        machine_file.write_text(
            _EXISTING
            + '\n[servers.anthropic]\nkind = "anthropic"\nprivate = false\nmax_parallel = 2\n',
            encoding="utf-8",
        )
        project = tmp_path / "proj"
        project.mkdir()
        (project / "specweaver.toml").write_text("[llm]\nprivate_only = true\n", encoding="utf-8")

        with pytest.raises(SettingsFileError):
            set_role("review", "claude-opus-5-5@anthropic", project_root=project)

        assert (project / "specweaver.toml").read_text(
            encoding="utf-8"
        ) == "[llm]\nprivate_only = true\n"
