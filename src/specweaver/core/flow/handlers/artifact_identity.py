# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Lineage identity for a written artifact: derive the UUID, inject the tag.

`TECH-016` §2. Four handlers hand-rolled "read back an existing uuid or mint one, then put the tag
at the top", and each copy is a place the convention can drift.

**This is the tail of an artifact write, not the write.** The ticket originally proposed one helper
taking a Pydantic model, and measuring the six call sites showed that fits two of them: `draft.py`
tags a file the drafter has *already* written, `generation.py` and `decomposition_artifacts.py` tag
content on its way to disk, and `lint_fix.py` carries a **pre-existing** uuid through an LLM
round-trip and must never mint one. Rendering a model, a dict, or an LLM's reply to bytes is
genuinely different work and stays where it is.

`infrastructure/llm/lineage` holds the string half (`extract_artifact_uuid`, `wrap_artifact_tag`)
and is deliberately pure. Anything that touches a `Path` belongs here instead.

Not in scope, and the reason: the `log_artifact_event` tail is near-identical at five sites and
looks like it belongs here too, but one of the five (`lint_fix.py:333`) opens `context.db` with no
`None` guard. Unifying it without the guard would copy that defect into shared code, and fixing it
here would be `TECH-036` landing inside `TECH-016`. `TECH-036` owns both halves together.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.lineage import extract_artifact_uuid, wrap_artifact_tag

if TYPE_CHECKING:
    from pathlib import Path


def derive_artifact_uuid(path: Path) -> str:
    """The artifact's lineage UUID: the one already on disk, or a freshly minted one.

    Reading back is what keeps a *regenerated* artifact a single lineage identity rather than a new
    one per run. A missing, untagged or unreadable file yields a new UUID — lineage is telemetry,
    and it must never be the reason a write fails.
    """
    try:
        existing = extract_artifact_uuid(path.read_text(encoding="utf-8"))
    except OSError:
        existing = None
    return existing or str(_uuid.uuid4())


def tag_content(content: str, artifact_uuid: str, language: str) -> str:
    """Return `content` with its lineage tag on the first line.

    A no-op when the content already carries a tag — including a *different* one, because two tags
    in one file is a lineage fork and the identity already recorded wins — or when `language` has
    no comment syntax (`wrap_artifact_tag` returns `None` for those, and corrupting the file is
    worse than leaving it untagged).
    """
    if extract_artifact_uuid(content):
        return content
    tag = wrap_artifact_tag(artifact_uuid, language)
    return f"{tag}\n{content}" if tag else content


def ensure_file_tagged(path: Path, language: str) -> str:
    """Tag a file that is already on disk, and return its lineage UUID.

    Rewrites nothing when the file is already tagged. A file that does not exist is **not
    created** — it still gets an identity, so a caller mid-write can carry one, but this function
    does not decide that an artifact exists.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return str(_uuid.uuid4())

    existing = extract_artifact_uuid(content)
    if existing:
        return existing

    artifact_uuid = str(_uuid.uuid4())
    tagged = tag_content(content, artifact_uuid, language)
    if tagged != content:
        path.write_text(tagged, encoding="utf-8")
    return artifact_uuid
