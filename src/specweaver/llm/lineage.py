# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Common utilities for artifact lineage tracking."""

from __future__ import annotations

import re

# Standard UUID regex: 32 hex chars with 4 hyphens
_UUID_PATTERN = re.compile(
    r"(?i)sw-artifact:\s*([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})"
)


def extract_artifact_uuid(content: str) -> str | None:
    """Extract the sw-artifact UUID from a file's content.

    Args:
        content: The text content of the file to scan.

    Returns:
        The 36-character UUID string if found, otherwise None.
    """
    if not content:
        return None

    match = _UUID_PATTERN.search(content)
    if match:
        return match.group(1).lower()
    return None


def wrap_artifact_tag(artifact_id: str, language: str) -> str | None:
    """Format the artifact tag into a language-specific comment block.

    Args:
        artifact_id: The UUID to inject.
        language: The target language (e.g. 'python', 'markdown').

    Returns:
        The formatted comment string, or None if the language
        does not natively support comments (e.g., json).
    """
    if not artifact_id or not language:
        return None

    language = language.lower()

    # Python-style
    if language in ("python", "yaml", "toml", "bash", "ruby", "sh", "yml"):
        return f"# sw-artifact: {artifact_id}"

    # C-style
    if language in ("javascript", "typescript", "java", "go", "rust", "js", "ts", "rs"):
        return f"// sw-artifact: {artifact_id}"

    # XML/Markdown style
    if language in ("markdown", "html", "xml", "md"):
        return f"<!-- sw-artifact: {artifact_id} -->"

    # SQL style
    if language in ("sql",):
        return f"-- sw-artifact: {artifact_id}"

    # Languages without standard comments or unrecognised languages
    # Return None so PromptBuilder skips tag injection rather than corrupting syntax
    return None
