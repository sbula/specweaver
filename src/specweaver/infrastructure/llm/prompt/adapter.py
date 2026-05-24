# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.infrastructure.llm.models import ProjectMetadata

from specweaver.infrastructure.llm._prompt_constants import detect_language
from specweaver.infrastructure.llm.escaping import apply_escaping, escape_xml_attribute

# Only allow alphanumeric, dashes, underscores, dots, and slashes in labels to prevent injection/spoofing
LABEL_REGEX = re.compile(r"^[a-zA-Z0-9_\-\./]+$")


def validate_label(label: str) -> None:
    stripped = label.strip()
    if not stripped:
        raise ValueError("Label cannot be empty or whitespace-only.")
    if not LABEL_REGEX.match(stripped):
        raise ValueError(
            f"Invalid label format: '{label}'. "
            "Must contain only alphanumeric characters, dashes, underscores, dots, or slashes."
        )


class StringPromptAdapter:
    def __init__(self, content: str, label: str, escaping: str = "cdata"):
        validate_label(label)
        self._content = content
        self._label = label.strip()
        self._escaping = escaping

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        escaped_label = escape_xml_attribute(self._label)
        payload = self._content
        if char_limit is not None:
            payload = payload[:char_limit] + "\n[truncated]"
        escaped_text = apply_escaping(payload, self._escaping)
        return f'<context label="{escaped_label}">\n{escaped_text}\n</context>'

    def get_prompt_label(self) -> str:
        return self._label


class FilePromptAdapter:
    def __init__(
        self,
        path: Path,
        label: str = "",
        role: str = "",
        escaping: str = "cdata",
        skeleton: bool = False,
        skeleton_files: dict[str, str] | None = None,
    ):
        test_label = label or path.name
        validate_label(test_label)
        self._path = path
        self._label = test_label.strip()
        self._role = role
        self._escaping = escaping
        self._skeleton = skeleton
        self._skeleton_files = skeleton_files or {}

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        # Enforce reasonable size limit on path to prevent AST parser resource abuse
        if self._path.stat().st_size > 10 * 1024 * 1024:
            raise ValueError(f"File too large: {self._path.name} exceeds 10MB limit.")

        content = self._path.read_text(encoding="utf-8")
        if self._skeleton:
            path_str = str(self._path)
            if path_str in self._skeleton_files:
                content = self._skeleton_files[path_str]
            else:
                try:
                    from specweaver.infrastructure.llm._skeleton import extract_ast_skeleton

                    content = extract_ast_skeleton(self._path, content)
                except Exception:
                    pass  # Graceful fallback to raw file content if AST parser fails

        if char_limit is not None:
            content = content[:char_limit] + "\n[truncated]"

        lang = detect_language(self._path)
        escaped_path = escape_xml_attribute(self._label)
        escaped_lang = escape_xml_attribute(lang)
        attrs = f'path="{escaped_path}" language="{escaped_lang}"'
        if self._role:
            escaped_role = escape_xml_attribute(self._role)
            attrs += f' role="{escaped_role}"'
        escaped_text = apply_escaping(content, self._escaping)
        return f"<file {attrs}>\n{escaped_text}\n</file>"

    def get_prompt_label(self) -> str:
        return self._label


class ProjectMetadataPromptAdapter:
    def __init__(self, metadata: ProjectMetadata):
        self._metadata = metadata

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        import json

        raw_dict = self._metadata.model_dump()
        yaml_content = f"project_metadata:\n{json.dumps(raw_dict, indent=2)}"
        if char_limit is not None:
            yaml_content = yaml_content[:char_limit] + "\n[truncated]"
        return f"<project_metadata>\n{yaml_content}\n</project_metadata>"

    def get_prompt_label(self) -> str:
        return "project_metadata"
