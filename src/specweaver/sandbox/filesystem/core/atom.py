# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""FileSystemAtom — Flow-level filesystem operations for the Engine.

The Engine uses FileSystemAtom to symlink caches into a worktree.

Uses EngineFileExecutor — no protected pattern restrictions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import Atom, AtomResult, AtomStatus
from specweaver.sandbox.filesystem.core.executor import EngineFileExecutor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class FileSystemAtomError(Exception):
    """Raised when a FileSystemAtom operation fails."""


class FileSystemAtom(Atom):
    """Flow-level filesystem operations for the Engine.

    Unlike FileSystemTool (agent-facing, role-restricted), FileSystemAtom
    is for the Engine only — it has unrestricted access including
    context.yaml writes.

    Args:
        cwd: Working directory (the target project root).
    """

    def __init__(self, cwd: Path) -> None:
        self._executor = EngineFileExecutor(cwd=cwd)
        self._cwd = cwd

    @property
    def cwd(self) -> Path:
        """The project root directory (read-only)."""
        return self._cwd

    def run(self, context: dict[str, Any]) -> AtomResult:
        """Dispatch to the appropriate intent based on context.

        The Engine provides a context dict with at minimum:
            intent: str — which operation to perform.
            (plus intent-specific keys)
        """
        intent = context.get("intent")
        if intent is None:
            logger.error("FileSystemAtom.run: missing 'intent' in context")
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'intent' in context.",
            )

        logger.info("FileSystemAtom.run: dispatching intent '%s'", intent)

        handler: Callable[[dict[str, Any]], AtomResult] | None = getattr(
            self,
            f"_intent_{intent}",
            None,
        )
        if handler is None:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Unknown intent: {intent!r}. Known: {sorted(self._known_intents())}",
            )

        return handler(context)

    def _known_intents(self) -> set[str]:
        """Return the set of known intent names."""
        prefix = "_intent_"
        return {name[len(prefix) :] for name in dir(self) if name.startswith(prefix)}

    # -- Intent implementations ----------------------------------------

    def _intent_symlink(self, context: dict[str, Any]) -> AtomResult:
        """Create a symlink for workspace caching.

        Context keys:
            target: str - absolute or relative path to link TO.
            link_name: str - path for the symlink TO CREATE.
        """
        target = context.get("target")
        link_name = context.get("link_name")

        if not target or not link_name:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'target' or 'link_name' in context for symlink intent.",
            )

        result = self._executor.symlink(target, link_name)
        if result.status != "success":
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Symlink failed: {result.error}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Created symlink {link_name} -> {target}",
        )
