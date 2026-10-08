# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Writes the machine settings file. The only module that does.

Edits go through `tomlkit`, so every comment, blank line and key order the user wrote survives. The
edited text is parsed with the same strict parser that reads it before anything is written, and the
write replaces the file in one step, so a command never leaves a broken file behind.
"""

from __future__ import annotations

import os
import stat
from typing import TYPE_CHECKING, Any

import tomlkit
import tomlkit.exceptions

from specweaver.core.config.bootstrap.llm_settings_loader import (
    PROJECT_FILE_NAME,
    machine_settings_path,
)
from specweaver.core.config.llm_settings import (
    LlmSettingsFiles,
    SettingsFileError,
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
    entry["usd_per_million_input"] = _tidy(usd_input)
    entry["usd_per_million_output"] = _tidy(usd_output)
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
        document = _parse(machine_text, machine_path)
        _assign_role(document.setdefault("roles", tomlkit.table()), role, value)
        machine_text = tomlkit.dumps(document)
        target, text = machine_path, machine_text
    else:
        document = _parse(project_text, project_path)
        llm = document.setdefault("llm", tomlkit.table())
        _assign_role(llm.setdefault("roles", tomlkit.table()), role, value)
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


def _assign_role(roles: Any, role: str, value: str) -> None:
    """A role written as a table keeps its other keys and comments; only its model changes."""
    if isinstance(roles.get(role), dict):
        roles[role]["model"] = value
    else:
        roles[role] = value


def _tidy(price: float) -> float:
    """A price converted from another currency, without float noise like 0.30000000000000004."""
    return float(f"{price:.12g}")


def _text(path: Path | None) -> str:
    # utf-8-sig: an editor's byte order mark is not part of the TOML. newline="": keep CRLF.
    if path is None or not path.is_file():
        return ""
    with path.open(encoding="utf-8-sig", newline="") as file:
        return file.read()


def _read(path: Path) -> TOMLDocument:
    return _parse(_text(path), path)


def _parse(text: str, path: Path) -> TOMLDocument:
    try:
        return tomlkit.parse(text)
    except tomlkit.exceptions.ParseError as exc:
        raise SettingsFileError(str(path), "(syntax)", exc.line, "not valid TOML") from exc


def _write(path: Path, document: TOMLDocument) -> None:
    text = tomlkit.dumps(document)
    parse_machine_file(text, str(path))  # refuses before anything is written
    _replace(path, text)


def _replace(path: Path, text: str) -> None:
    """Write in one step: the file is either the old text or the new, never half of each."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".toml.tmp")
    if path.is_file() and "\r\n" in _text(path):
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    temporary.write_text(text, encoding="utf-8", newline="")
    if path.is_file():
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
    os.replace(temporary, path)
