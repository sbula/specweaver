# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Writes the machine settings file. The only module that does.

Edits go through `tomlkit`, so every comment, blank line and key order the user wrote survives. The
edited text is parsed with the same strict parser that reads it before anything is written, and the
write replaces the file in one step, so a command never leaves a broken file behind.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import tomlkit

from specweaver.core.config.bootstrap.llm_settings_loader import (
    PROJECT_FILE_NAME,
    machine_settings_path,
)
from specweaver.core.config.llm_settings import (
    LlmSettingsFiles,
    parse_machine_file,
    resolve_roles,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tomlkit import TOMLDocument

_PRICE_KEYS = ("usd_per_million_input", "usd_per_million_output")


def set_model_price(model: str, usd_input: float, usd_output: float) -> Path:
    """Set a model's price, USD per 1M tokens, under `[models."<model>"]`."""
    path = machine_settings_path()
    document = _read(path)
    models = document.setdefault("models", tomlkit.table(is_super_table=True))
    entry = models.setdefault(model, tomlkit.table())
    entry["usd_per_million_input"] = usd_input
    entry["usd_per_million_output"] = usd_output
    _write(path, document)
    return path


def set_role(role: str, value: str, *, project_root: Path | None = None) -> Path:
    """Set a role to `"model@server"` — in the project's `[llm.roles]` when `project_root` is given,
    else in the machine file's `[roles]`.

    Both files are parsed and the roles resolved before anything is written, so a role on a server
    nobody defined, or on a hosted server in a private-only project, is refused, file untouched.
    """
    machine_path = machine_settings_path()
    project_path = project_root / PROJECT_FILE_NAME if project_root else None
    machine_text = _text(machine_path)
    project_text = _text(project_path)
    if project_path is None:
        document = tomlkit.parse(machine_text)
        document.setdefault("roles", tomlkit.table())[role] = value
        machine_text = tomlkit.dumps(document)
        target, text = machine_path, machine_text
    else:
        document = tomlkit.parse(project_text)
        llm = document.setdefault("llm", tomlkit.table())
        llm.setdefault("roles", tomlkit.table())[role] = value
        project_text = tomlkit.dumps(document)
        target, text = project_path, project_text
    files = LlmSettingsFiles.from_texts(
        machine_text=machine_text,
        machine_source=str(machine_path),
        project_text=project_text,
        project_source=str(project_path) if project_path else "(no project)",
    )
    resolve_roles(files)  # refuses before anything is written
    _replace(target, text)
    return target


def clear_model_price(model: str) -> bool:
    """Remove a model's price; its other facts stay. `False` when it had none."""
    path = machine_settings_path()
    document = _read(path)
    models = document.get("models", {})
    entry = models.get(model)
    if entry is None or not any(key in entry for key in _PRICE_KEYS):
        return False
    for key in _PRICE_KEYS:
        entry.pop(key, None)
    if not entry:
        models.pop(model)
    _write(path, document)
    return True


def _text(path: Path | None) -> str:
    return path.read_text(encoding="utf-8") if path is not None and path.is_file() else ""


def _read(path: Path) -> TOMLDocument:
    return tomlkit.parse(_text(path))


def _write(path: Path, document: TOMLDocument) -> None:
    text = tomlkit.dumps(document)
    parse_machine_file(text, str(path))  # refuses before anything is written
    _replace(path, text)


def _replace(path: Path, text: str) -> None:
    """Write in one step: the file is either the old text or the new, never half of each."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
