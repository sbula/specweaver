# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Workspace boundary — dynamic path enforcement for research tools.

Defines which paths an agent can access, based on its pipeline phase:
- Feature-level: entire project root
- Component-level: microservice folder + API contracts of neighbors
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.flow._base import RunContext

logger = logging.getLogger(__name__)


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
        raise WorkspaceBoundaryError(msg)

    def resolve_relative(self, relative: str) -> Path:
        """Resolve a relative path against the primary root.

        Validates the resolved path is within boundaries.
        """
        resolved = (self.roots[0] / relative).resolve()
        return self.validate_path(resolved)

    @classmethod
    def from_run_context(cls, context: RunContext) -> WorkspaceBoundary:
        """Build boundary from pipeline context.

        - If workspace_roots is set (by decomposition): use those
        - Otherwise: use project_path (feature-level boundary)
        - If api_contract_paths is set: include as read-only paths
        """
        if context.workspace_roots:
            roots = [Path(r) for r in context.workspace_roots]
            logger.debug(
                "WorkspaceBoundary: component-level, roots=%s",
                [str(r) for r in roots],
            )
        else:
            roots = [context.project_path]
            logger.debug(
                "WorkspaceBoundary: feature-level, root=%s",
                context.project_path,
            )

        api_paths: list[Path] | None = None
        if context.api_contract_paths:
            api_paths = [Path(p) for p in context.api_contract_paths]
            logger.debug(
                "WorkspaceBoundary: api_paths=%s",
                [str(p) for p in api_paths],
            )

        return cls(roots=roots, api_paths=api_paths)

    @staticmethod
    def _is_subpath(child: Path, parent: Path) -> bool:
        """Check if child is a subpath of parent (resolved paths)."""
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False
