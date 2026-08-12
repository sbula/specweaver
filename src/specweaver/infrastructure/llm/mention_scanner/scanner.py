# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Mention scanner — extract file/spec references from LLM response text.

Pure-logic module: no I/O, no filesystem access.  Produces candidate path
strings that the consuming handler resolves against the project workspace.

Inspired by Aider's ``check_for_file_mentions()``.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------

# Minimum fenced-code-block size to skip (lines).  Blocks ≤ this are scanned.
_LARGE_BLOCK_LINE_THRESHOLD = 5

# Patterns that look like file references
_BACKTICK_PATH = re.compile(r"`([^`\n]+\.[a-zA-Z]{1,5})`")
_QUOTED_PATH = re.compile(r"""(?:"|')([^"'\n]+\.[a-zA-Z]{1,5})(?:"|')""")
_BARE_SPEC = re.compile(r"\b(\S+_spec\.(?:md|yaml))\b")
_RELATIVE_PATH = re.compile(r"\b((?:[\w.-]+/)+[\w.-]+\.[a-zA-Z]{1,5})\b")

# Patterns to REJECT
_URL_PREFIX = re.compile(r"^https?://", re.IGNORECASE)
_URL_INLINE = re.compile(r"https?://\S+", re.IGNORECASE)

# Files to filter unless given as a full path (with /)
_FILTER_BASENAMES = {"__init__.py"}

# Fenced code block delimiters
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_mentions(text: str) -> list[str]:
    """Extract candidate file/spec path strings from LLM response text.

    This is a **pure function** — no I/O, no disk access.  It returns raw
    candidate strings that must be resolved and validated by the caller.

    Filtering rules:
    - URLs (``http://``, ``https://``) are excluded.
    - ``__init__.py`` is excluded unless a full path is given.
    - Content inside large fenced code blocks (>{threshold} lines) is skipped.
    - Duplicates are collapsed (preserving first-seen order).

    Args:
        text: The full LLM response text to scan.

    Returns:
        Deduplicated list of candidate path strings, in order of first
        appearance.
    """
    logger.debug("Extracting mentions from text length: %d", len(text))
    # Pre-processing: strip URLs so sub-paths don't match as file refs
    cleaned = _URL_INLINE.sub("", text)
    # Strip large fenced code blocks before scanning
    cleaned = _strip_large_code_blocks(cleaned)

    candidates: list[str] = []
    seen: set[str] = set()

    for pattern in (_BACKTICK_PATH, _QUOTED_PATH, _BARE_SPEC, _RELATIVE_PATH):
        for match in pattern.finditer(cleaned):
            candidate = match.group(1).strip()
            if _should_include(candidate) and candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)

    logger.debug("Extracted %d mention candidates", len(candidates))
    return candidates


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _closes_fence(line: str, fence_marker: str) -> bool:
    """Whether this line closes the open fence.

    A closing fence is the marker and nothing else — the one-character slack allows a stray
    trailing character without matching a *nested* opening fence that carries a language tag.
    """
    stripped = line.strip()
    return stripped.startswith(fence_marker) and len(stripped) <= len(fence_marker) + 1


def _kept_block(block_lines: list[str]) -> list[str]:
    """The block's lines if it is small enough to keep, else nothing.

    Small blocks often carry real file references; large ones are generated output and produce
    false positives, which is the whole reason this stripping exists.
    """
    content_lines = block_lines[1:-1]  # excluding both fences
    return block_lines if len(content_lines) <= _LARGE_BLOCK_LINE_THRESHOLD else []


def _strip_large_code_blocks(text: str) -> str:
    """Remove fenced code blocks longer than the threshold.

    Small blocks (≤ threshold lines) are kept because they often contain
    meaningful file references.  Large blocks are typically generated code
    output and produce false-positive matches.
    """
    result: list[str] = []
    block_lines: list[str] = []
    fence_marker: str | None = None

    for line in text.split("\n"):
        if fence_marker is None:
            opened = _FENCE_OPEN.match(line.strip())
            if opened:
                fence_marker = opened.group(1)[:3]  # ``` or ~~~
                block_lines = [line]
            else:
                result.append(line)
            continue

        block_lines.append(line)
        if _closes_fence(line, fence_marker):
            result.extend(_kept_block(block_lines))
            fence_marker = None
            block_lines = []

    # An unclosed block keeps its lines: truncated output is still worth scanning.
    result.extend(block_lines)
    return "\n".join(result)


def _should_include(candidate: str) -> bool:
    """Return True if the candidate looks like a valid file reference."""
    # Reject URLs
    if _URL_PREFIX.match(candidate):
        return False

    # Reject bare __init__.py (no directory prefix)
    basename = candidate.rsplit("/", 1)[-1] if "/" in candidate else candidate
    if basename in _FILTER_BASENAMES and "/" not in candidate:
        return False

    # Reject candidates that are clearly not paths (too short)
    return len(candidate) >= 4
