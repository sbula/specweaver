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

from specweaver.core.config.bootstrap.llm_settings_loader import machine_settings_path
from specweaver.core.config.llm_settings import parse_machine_file

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


def _read(path: Path) -> TOMLDocument:
    return tomlkit.parse(path.read_text(encoding="utf-8") if path.is_file() else "")


def _write(path: Path, document: TOMLDocument) -> None:
    text = tomlkit.dumps(document)
    parse_machine_file(text, str(path))  # refuses before anything is written
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".toml.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
