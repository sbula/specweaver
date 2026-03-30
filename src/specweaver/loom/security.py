# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Security models — boundaries, access controls, and role intents."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.flow._base import RunContext

logger = logging.getLogger(__name__)


class AccessMode(StrEnum):
    """Access level for a folder grant."""

    READ = "read"  # list, read, search
    WRITE = "write"  # read + write + edit
    FULL = "full"  # read + write + edit + create + delete


# Permission hierarchy: which modes allow which operations
MODE_ALLOWS_READ: frozenset[AccessMode] = frozenset(
    {AccessMode.READ, AccessMode.WRITE, AccessMode.FULL}
)
MODE_ALLOWS_WRITE: frozenset[AccessMode] = frozenset({AccessMode.WRITE, AccessMode.FULL})
MODE_ALLOWS_CREATE: frozenset[AccessMode] = frozenset({AccessMode.FULL})
MODE_ALLOWS_DELETE: frozenset[AccessMode] = frozenset({AccessMode.FULL})


@dataclass(frozen=True)
class FolderGrant:
    """A single folder access grant.

    Args:
        path: Relative path from project root (e.g., "src/domain/billing").
        mode: Access level (READ, WRITE, or FULL).
        recursive: If True, grant covers all subdirectories.
    """

    path: str
    mode: AccessMode
    recursive: bool


class WorkspaceBoundaryError(Exception):
    """Raised when a path escapes the workspace boundary."""


class WorkspaceBoundary:
    """Defines and enforces which paths an agent can access.

    Args:
        roots: One or more allowed root directories.
        api_paths: Read-only paths for neighboring API contracts
                   (visible but not searchable in depth).
    """

    def __init__(
        self,
        roots: list[Path],
        api_paths: list[Path] | None = None,
    ) -> None:
        if not roots:
            msg = "WorkspaceBoundary requires at least one root directory"
            raise ValueError(msg)
        self.roots = [r.resolve() for r in roots]
        self.api_paths = [p.resolve() for p in (api_paths or [])]

    def validate_path(self, requested: Path) -> Path:
        """Resolve and validate a path is within boundaries.

        Returns the resolved absolute path.
        Raises WorkspaceBoundaryError if path escapes boundaries.
        """
        resolved = requested.resolve()

        # Check against all roots
        for root in self.roots:
            if resolved == root or self._is_subpath(resolved, root):
                return resolved

        # Check against API paths (read-only access)
        for api_path in self.api_paths:
            if resolved == api_path or self._is_subpath(resolved, api_path):
                return resolved

        msg = (
            f"Path '{resolved}' is outside workspace boundaries "
            f"(roots: {[str(r) for r in self.roots]})"
        )
        logger.warning("WorkspaceBoundary.validate_path: %s", msg)
        raise WorkspaceBoundaryError(msg)

    def resolve_relative(self, relative: str) -> Path:
        """Resolve a relative path against the primary root."""
        resolved = (self.roots[0] / relative).resolve()
        return self.validate_path(resolved)

    @classmethod
    def from_run_context(cls, context: RunContext) -> WorkspaceBoundary:
        """Build boundary from pipeline context."""
        if context.workspace_roots:
            roots = [Path(r) for r in context.workspace_roots]
        else:
            roots = [context.project_path]

        api_paths: list[Path] | None = None
        if context.api_contract_paths:
            api_paths = [Path(p) for p in context.api_contract_paths]

        return cls(roots=roots, api_paths=api_paths)

    @staticmethod
    def _is_subpath(child: Path, parent: Path) -> bool:
        """Check if child is a subpath of parent (resolved paths)."""
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False
