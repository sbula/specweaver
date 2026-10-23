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
from specweaver.core.config.llm_settings import parse_machine_file, parse_project_llm
from specweaver.core.config.settings_file import SettingsFileError

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
            + '\n[servers.anthropic]\nkind = "anthropic"\napi_key_env = "ANTHROPIC_API_KEY"\nprivate = false\nmax_parallel = 2\n',
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


_ROLE_TABLE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles.review]   # the reviewer needs room
model = "old-model@gb10"
max_output_tokens = 4000   # keep this
"""


def test_set_role_on_a_role_table_changes_only_its_model(machine_file: Path) -> None:
    machine_file.write_text(_ROLE_TABLE, encoding="utf-8")

    set_role("review", "qwen3-coder-next@gb10")

    text = machine_file.read_text(encoding="utf-8")
    assert "# the reviewer needs room" in text
    assert "max_output_tokens = 4000   # keep this" in text
    assert 'model = "qwen3-coder-next@gb10"' in text


@pytest.mark.parametrize(
    "write", [lambda: set_role("review", "m@gb10"), lambda: clear_model_price("m")]
)
def test_a_broken_file_is_refused_naming_its_line(machine_file: Path, write) -> None:
    machine_file.write_text("[servers.gb10\nkind = 1\n", encoding="utf-8")

    with pytest.raises(SettingsFileError) as caught:
        write()

    assert caught.value.line == 1
    assert machine_file.read_text(encoding="utf-8") == "[servers.gb10\nkind = 1\n"


def test_a_file_saved_with_a_byte_order_mark_is_read(machine_file: Path) -> None:
    machine_file.write_text(_EXISTING, encoding="utf-8-sig")

    set_model_price("qwen3-coder-next", 1.0, 2.0)

    facts = parse_machine_file(machine_file.read_text(encoding="utf-8"), "x").models[
        "qwen3-coder-next"
    ]
    assert facts.usd_per_million_input == 1.0


def test_the_loader_reads_a_file_saved_with_a_byte_order_mark(machine_file: Path) -> None:
    from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings

    machine_file.write_text(_EXISTING, encoding="utf-8-sig")

    assert "gb10" in load_llm_settings(None).machine.servers


def test_windows_line_endings_survive_an_edit(machine_file: Path) -> None:
    machine_file.write_bytes(_EXISTING.replace("\n", "\r\n").encode("utf-8"))

    set_model_price("qwen3-coder-next", 1.0, 2.0)

    raw = machine_file.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n")


def test_the_files_permissions_survive_an_edit(machine_file: Path) -> None:
    import os
    import stat

    machine_file.write_text(_EXISTING, encoding="utf-8")
    os.chmod(machine_file, 0o600)

    set_model_price("qwen3-coder-next", 1.0, 2.0)

    assert stat.S_IMODE(machine_file.stat().st_mode) == 0o600


def test_a_price_is_stored_without_float_noise(machine_file: Path) -> None:
    set_model_price("m", 0.1 + 0.2, 1.0 / 3.0)

    text = machine_file.read_text(encoding="utf-8")
    assert "0.30000000000000004" not in text
    assert "usd_per_million_input = 0.3\n" in text


@pytest.mark.parametrize("price", [float("inf"), float("nan")])
def test_an_infinite_or_missing_number_is_refused(machine_file: Path, price: float) -> None:
    with pytest.raises(SettingsFileError):
        set_model_price("m", price, 1.0)

    assert not machine_file.exists()


def test_an_exchange_rate_dated_in_the_future_is_refused() -> None:
    from datetime import date, timedelta

    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    text = f'[currency]\ncode = "CHF"\nper_usd = 0.8\nrate_date = {tomorrow}\n'

    with pytest.raises(SettingsFileError, match="future"):
        parse_machine_file(text, "settings.toml")
