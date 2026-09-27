# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads the LLM settings files. The only module that does.

The machine file lives beside the data (`SPECWEAVER_DATA_DIR`, else `~/.specweaver`); the project
section is `[llm]` in the project's `specweaver.toml`. A missing file is not an error — it means
built-in defaults or an empty choice. A broken one is: it refuses, naming its path and line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.core.config.paths import specweaver_root

if TYPE_CHECKING:
    from pathlib import Path

MACHINE_FILE_NAME = "settings.toml"
PROJECT_FILE_NAME = "specweaver.toml"


def machine_settings_path() -> Path:
    return specweaver_root() / MACHINE_FILE_NAME


def load_llm_settings(project_root: Path | None) -> LlmSettingsFiles:
    """Both settings files, parsed and ready to layer."""
    machine_path = machine_settings_path()
    project_path = project_root / PROJECT_FILE_NAME if project_root else None
    return LlmSettingsFiles.from_texts(
        machine_text=_read(machine_path),
        machine_source=str(machine_path),
        project_text=_read(project_path),
        project_source=str(project_path) if project_path else "(no project)",
    )


def _read(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")
