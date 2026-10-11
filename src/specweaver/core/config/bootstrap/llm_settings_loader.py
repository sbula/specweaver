# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads the LLM settings files. The only module that does.

The machine file lives beside the data (`SPECWEAVER_DATA_DIR`, else `~/.specweaver`); the project
section is `[llm]` in the project's `specweaver.toml`. A missing file is not an error — it is an
empty one, and a command that needs a model then refuses. A broken one refuses, naming its line.

API keys come only from `keys.env` beside the machine file, which only its owner may read.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dotenv import dotenv_values

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.core.config.paths import specweaver_root

if TYPE_CHECKING:
    from pathlib import Path

MACHINE_FILE_NAME = "settings.toml"
KEYS_FILE_NAME = "keys.env"
PROJECT_FILE_NAME = "specweaver.toml"


def machine_settings_path() -> Path:
    return specweaver_root() / MACHINE_FILE_NAME


def load_llm_settings(project_root: Path | None) -> LlmSettingsFiles:
    """Both settings files, parsed and ready to layer."""
    machine_path = machine_settings_path()
    project_path = project_root / PROJECT_FILE_NAME if project_root else None
    keys_path = specweaver_root() / KEYS_FILE_NAME
    return LlmSettingsFiles.from_texts(
        machine_text=_read(machine_path),
        machine_source=str(machine_path),
        project_text=_read(project_path),
        project_source=str(project_path) if project_path else "(no project)",
        project_root=project_root,
        keys=load_keys(keys_path),
        keys_source=str(keys_path),
    )


def load_keys(path: Path) -> dict[str, str]:
    """The keys in `path` by variable name; none when it is missing. Refused if others can read it."""
    if not path.is_file():
        return {}
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise SettingsFileError(
            str(path), "(file mode)", 0, f"other users can read this key file; run chmod 600 {path}"
        )
    return {name: value for name, value in dotenv_values(path).items() if value}


def _read(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")
