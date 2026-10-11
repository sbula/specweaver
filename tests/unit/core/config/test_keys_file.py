# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""API keys live in one file, `keys.env` beside the settings; the settings only name them.

Proves: C-FLOW-13 FR-7, NFR-2

Agreed 2026-10-11: keys come from `~/.specweaver/keys.env` only — never from the shell, never from
a repository — and the file is refused unless only its owner can read it.

| Bucket | Case |
|---|---|
| Happy | `NAME=value` lines are read; a server's `api_key_env` finds its key there |
| Boundary | a missing file is no keys; comments, blanks, `export` and quotes are handled |
| Degradation | a key the file lacks refuses the command, naming the variable and the file |
| Hostile | a file others can read is refused (chmod 600); a key set only in the shell is ignored |
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.llm_settings_loader import load_keys, load_llm_settings
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.resolve import RoleResolver

if TYPE_CHECKING:
    from pathlib import Path

_MACHINE = """\
[servers.gemini]
kind = "gemini"
api_key_env = "MY_GEMINI"
private = false
max_parallel = 1

[roles]
default = { model = "gemini-3.8-flash@gemini", max_output_tokens = 100 }
"""


def _keys(tmp_path: Path, text: str, mode: int = 0o600) -> Path:
    path = tmp_path / "keys.env"
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)
    return path


def test_lines_are_read(tmp_path: Path) -> None:
    path = _keys(tmp_path, '# mine\n\nMY_GEMINI="abc"\nexport OTHER=x y\n')

    assert load_keys(path) == {"MY_GEMINI": "abc", "OTHER": "x y"}


def test_a_missing_file_is_no_keys(tmp_path: Path) -> None:
    assert load_keys(tmp_path / "keys.env") == {}


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604])
def test_a_file_others_can_read_is_refused(tmp_path: Path, mode: int) -> None:
    path = _keys(tmp_path, "MY_GEMINI=abc\n", mode)

    with pytest.raises(SettingsFileError) as caught:
        load_keys(path)

    assert "chmod 600" in caught.value.message
    assert "abc" not in str(caught.value)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    return tmp_path


def _resolver(data_dir: Path) -> RoleResolver:
    return RoleResolver(load_llm_settings(None), telemetry_project="p", budget=SpendBudget())


def test_the_server_gets_its_key_from_the_file(data_dir: Path) -> None:
    _keys(data_dir, "MY_GEMINI=from-the-file\n")

    adapter, _config = _resolver(data_dir).for_role("review")

    assert adapter._adapter._wrapped._api_key == "from-the-file"


def test_a_key_only_in_the_shell_is_ignored(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MY_GEMINI", "from-the-shell")

    with pytest.raises(SettingsFileError) as caught:
        _resolver(data_dir).require(["review"])

    assert "MY_GEMINI" in caught.value.message
    assert "keys.env" in caught.value.message
    assert "from-the-shell" not in str(caught.value)


def test_the_files_keys_are_masked_in_prompts(data_dir: Path) -> None:
    _keys(data_dir, "MY_GEMINI=sk-file-secret-0123456789\n")

    adapter, _config = _resolver(data_dir).for_role("review")

    assert "sk-file-secret-0123456789" not in adapter._redactor.text(
        "the key is sk-file-secret-0123456789"
    )
