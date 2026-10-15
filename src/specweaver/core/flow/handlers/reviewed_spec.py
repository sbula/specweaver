# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which version of a spec its last accepted review saw, kept in the project's scenario store."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from typing import TYPE_CHECKING

from specweaver.commons.timestamps import now_iso

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def spec_sha(spec_path: Path) -> str:
    """The spec's SHA-256; "" when it cannot be read."""
    try:
        return hashlib.sha256(spec_path.read_text(encoding="utf-8").encode()).hexdigest()
    except OSError:
        return ""


def _record_path(context: RunContext) -> Path | None:
    from specweaver.core.flow.handlers.scenario_store import scenario_store

    store = scenario_store(context)
    return store / "reviewed" / f"{context.spec_path.stem}.json" if store else None


def record_review(context: RunContext) -> None:
    """Keep the accepted spec's fingerprint; written whole, so a crash leaves the old one."""
    target = _record_path(context)
    if target is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial")
    record = {"sha256": spec_sha(context.spec_path), "reviewed_at": now_iso()}
    partial.write_text(json.dumps(record), encoding="utf-8")
    os.replace(partial, target)
    logger.info("Recorded the accepted review of '%s'", context.spec_path.name)


def review_refusal(context: RunContext, *, without_store: str | None = "refuse") -> str | None:
    """Why the spec is not the one its last accepted review saw; None when it is.

    `without_store=None` passes a project with no store: the dual run refuses those already.
    """
    target = _record_path(context)
    if target is None and without_store is None:
        return None
    command = f"run `sw review {context.spec_path}`"
    if target is None or not target.is_file():
        return f"the spec has no accepted review; {command} first"
    try:
        reviewed = json.loads(target.read_text(encoding="utf-8")).get("sha256")
    except (OSError, ValueError):
        reviewed = None
    if reviewed != spec_sha(context.spec_path):
        return f"the spec changed since its review; {command}, then resume"
    return None
