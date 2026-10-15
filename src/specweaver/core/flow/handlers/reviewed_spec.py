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


def _write_whole(target: Path, record: dict[str, str]) -> None:
    """Written whole, so a crash leaves the old record."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial")
    partial.write_text(json.dumps(record), encoding="utf-8")
    os.replace(partial, target)


def _read(target: Path) -> dict[str, str]:
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return record if isinstance(record, dict) else {}


def record_review(context: RunContext) -> None:
    """Keep the accepted spec's fingerprint."""
    target = _record_path(context)
    if target is None:
        return
    _write_whole(target, {"sha256": spec_sha(context.spec_path), "reviewed_at": now_iso()})
    logger.info("Recorded the accepted review of '%s'", context.spec_path.name)


def _contract_sha(context: RunContext) -> str:
    from pathlib import Path

    paths = [Path(p) for p in context.graph.api_contract_paths or []]
    return next((spec_sha(p) for p in paths if p.is_file()), "")


def _kept_path(context: RunContext) -> Path | None:
    from specweaver.core.flow.handlers.scenario_store import scenario_store

    store = scenario_store(context)
    return store / "kept" / f"{context.spec_path.stem}.json" if store else None


def keep_set(context: RunContext) -> None:
    """The set passed: keep it with the spec and contract it was made from."""
    target = _kept_path(context)
    if target is None:
        return
    record = {
        "spec_sha256": spec_sha(context.spec_path),
        "contract_sha256": _contract_sha(context),
        "kept_at": now_iso(),
    }
    _write_whole(target, record)
    logger.info("Kept the scenario set of '%s'", context.spec_path.name)


def kept_set_fresh(context: RunContext) -> bool:
    """A kept set made from this spec and this contract, whose tests are still in the store."""
    target = _kept_path(context)
    if target is None or not target.is_file():
        return False
    record = _read(target)
    stem = context.spec_path.stem.removesuffix("_spec")
    tests = target.parent.parent / "generated"
    return (
        record.get("spec_sha256") == spec_sha(context.spec_path)
        and record.get("contract_sha256") == _contract_sha(context)
        and tests.is_dir()
        and any(tests.glob(f"*{stem}*"))
    )


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
    if _read(target).get("sha256") != spec_sha(context.spec_path):
        return f"the spec changed since its review; {command}, then resume"
    return None
