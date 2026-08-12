# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An artifact's lineage: its identity on disk, and its events in the telemetry DB.

`TECH-016` §2, the tail of an artifact write. Two halves, both hand-rolled across the handlers:

- **identity** — read back an existing uuid or mint one, then put the tag at the top (4 sites)
- **events** — open a session and record what happened to the artifact (**7** sites)

**The head is deliberately not here.** The ticket originally proposed one helper taking a Pydantic
model; measuring the call sites showed that fits two of them. `draft.py` tags a file the drafter
has *already* written, `generation.py` and `decomposition_artifacts.py` tag content on its way to
disk, and `lint_fix.py` carries a **pre-existing** uuid through an LLM round-trip and must never
mint one. Rendering a model, a dict, or an LLM's reply to bytes is genuinely different work.

`infrastructure/llm/lineage` holds the string half (`extract_artifact_uuid`, `wrap_artifact_tag`)
and is deliberately pure. Anything touching a `Path` or the database belongs here instead.
"""

from __future__ import annotations

import logging
import uuid as _uuid
from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.lineage import extract_artifact_uuid, wrap_artifact_tag

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


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


async def log_artifact_lineage(
    context: RunContext,
    artifact_uuid: str,
    event_type: str,
    *,
    parent_id: str | None = None,
    model_id: str = "unknown",
) -> None:
    """Record one lineage event. **Never raises**, and does nothing without a telemetry DB.

    Lineage is telemetry, and by the time it runs the artifact has already been paid for with an
    LLM call and durably written to disk. Letting a database problem propagate hands it to
    ``execute``'s ``except Exception``, which returns ``ERROR`` with no ``output`` — **discarding
    work that succeeded**, and pointing the reader at the LLM rather than at the telemetry config.

    That contract was written for the decomposition handler after a real CB-1 pre-commit failure
    against a non-bootstrapped database (2026-07-26), and it was never generalised: of the seven
    sites this replaces, one had the guard *and* the ``try``, five had only the guard, and
    ``lint_fix.py`` had **neither** — `TECH-036`. The failure is logged at exception level so it
    stays loud while the run continues.
    """
    if not context.db:
        return

    from specweaver.core.flow.store import FlowRepository

    try:
        async with context.db.async_session_scope() as session:
            repo = FlowRepository(session)
            await repo.log_artifact_event(
                artifact_id=artifact_uuid,
                parent_id=parent_id,
                run_id=context.run.run_id or "pipeline_run",
                event_type=event_type,
                model_id=model_id,
            )
    except Exception:
        logger.exception(
            "[run_id=%s] Lineage event %r failed for artifact %s — the artifact is already on "
            "disk, so the step continues",
            context.run.run_id,
            event_type,
            artifact_uuid,
        )
