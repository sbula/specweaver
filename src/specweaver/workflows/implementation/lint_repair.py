# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Asks the model to fix a file's lint errors, in the file's language, keeping its lineage tag."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from specweaver.commons.lineage import extract_artifact_uuid, tag_content, wrap_artifact_tag
from specweaver.infrastructure.llm.models import Message, Role
from specweaver.workflows.implementation.generator import strip_fences
from specweaver.workflows.implementation.languages import language_guide

if TYPE_CHECKING:
    from pathlib import Path


async def repair_lint(
    adapter: Any,
    config: Any,
    code: str,
    lint_errors: list[dict[str, object]],
    language: str,
    project_dir: Path,
) -> str:
    """The model's fix of `code` for `lint_errors`; errors from the adapter propagate."""
    name = language_guide(language, project_dir).name
    errors = "\n".join(
        f"- {e.get('file', '?')}:{e.get('line', '?')} [{e.get('code', '?')}] {e.get('message', '')}"
        for e in lint_errors
    )
    prompt = (
        f"Fix the following lint errors in this {name} file.\n\n"
        f"## Lint Errors\n{errors}\n\n"
        f"## Current Code\n```{language}\n{code}\n```\n\n"
        f"Return ONLY the fixed {name} code, no explanations."
    )
    # Never mint an id here: the file's identity was minted when it was generated.
    artifact_uuid = extract_artifact_uuid(code)
    tag = wrap_artifact_tag(artifact_uuid, language) if artifact_uuid else None
    if tag:
        prompt += (
            f"\n\nIMPORTANT: You MUST include the exact string '{tag}' physically at the very top "
            "of your output file."
        )

    response = await adapter.generate([Message(role=Role.USER, content=prompt)], config)
    fixed = strip_fences(response.text)
    # The model may not reproduce the tag it was asked to keep.
    return tag_content(fixed, artifact_uuid, language) if artifact_uuid else fixed
