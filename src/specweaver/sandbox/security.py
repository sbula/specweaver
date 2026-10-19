# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Security models — boundaries, access controls, and role intents."""

from __future__ import annotations

import logging
import os
import posixpath
from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from specweaver.core.config.doc_policy import DocPolicy, DocRule

if TYPE_CHECKING:
    from collections.abc import Sequence

    from specweaver.core.flow.handlers.run_context import RunContext

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

    def __post_init__(self) -> None:
        """Reject a grant that names no directory.

        An empty path is not "the project root" — it is a bug or an unset config, and a security
        primitive should fail closed on it. It was also not inert: the matcher compares path
        segments against an absolute path, so on POSIX the leading `''` of `/tmp/proj/x` matched an
        empty grant and granted the whole project, while on Windows `C:/proj/x` never matched.
        One configuration, two security postures.

        To grant the whole project, pass the project root's absolute path — which already works.
        """
        if not self.path.strip():
            msg = (
                "FolderGrant.path is empty. A grant must name a directory; pass the project "
                "root's absolute path to grant the whole project."
            )
            raise ValueError(msg)


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
        """Build boundary from pipeline context: the project root, and its API paths read-only."""
        roots = [context.project_path]

        api_paths: list[Path] | None = None
        if context.graph.api_contract_paths:
            api_paths = [Path(p) for p in context.graph.api_contract_paths]

        return cls(roots=roots, api_paths=api_paths)

    @staticmethod
    def _is_subpath(child: Path, parent: Path) -> bool:
        """Check if child is a subpath of parent (resolved paths)."""
        try:
            child.relative_to(parent)
            return True
        except ValueError:  # expected: not a subpath
            return False


class ReadOnlyWorkspaceBoundary(WorkspaceBoundary):
    """Workspace boundary for zero-write agents (arbiters, auditors).

    Has no write roots. All accessible paths are in api_paths (read-only).
    Uses validate_path() inherited from WorkspaceBoundary — it already
    checks api_paths when roots is empty.
    """

    def __init__(self, api_paths: list[Path]) -> None:
        if not api_paths:
            msg = "ReadOnlyWorkspaceBoundary requires at least one api_path"
            raise ValueError(msg)
        # Bypass parent __init__ — parent raises ValueError on empty roots
        self.roots: list[Path] = []
        self.api_paths = [p.resolve() for p in api_paths]

    @property
    def is_read_only(self) -> bool:
        """Always True — this boundary has no write roots."""
        return True


# ---------------------------------------------------------------------------
# Grant matching — the one copy every agent tool uses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TaskGrant:
    """FULL on the files under `root` that one task may write: the ones the merge would keep.

    `files` are repo-relative entries, paths or globs (`path_allowed`). An entry that is empty,
    absolute or holds `..` stops the grant from being built: it would reach past the project.
    """

    root: str
    files: tuple[str, ...]
    mode: AccessMode = AccessMode.FULL

    def __post_init__(self) -> None:
        for entry in self.files:
            parts = entry.replace("\\", "/").split("/")
            if not entry.strip() or os.path.isabs(entry) or entry[1:2] == ":" or ".." in parts:
                msg = f"task file {entry!r} must be a path inside the project"
                raise ValueError(msg)

    def covers(self, absolute: str) -> bool:
        root = self.root.replace("\\", "/").rstrip("/")
        if not absolute.startswith(root + "/"):
            return False
        return merge_keeps(absolute[len(root) + 1 :], list(self.files))


def path_allowed(path: str, patterns: list[str]) -> bool:
    """Whether a repo-relative path matches an allow-list entry: a path, or a glob in which `*`
    stays inside one folder and `**` spans any number of folders."""
    parts = path.split("/")
    if ".." in parts:
        return False
    return any(_match(parts, pattern.split("/")) for pattern in patterns)


def _match(parts: list[str], pattern: list[str]) -> bool:
    if not pattern:
        return not parts
    if pattern[0] == "**":
        return any(_match(parts[i:], pattern[1:]) for i in range(len(parts) + 1))
    return bool(parts) and fnmatchcase(parts[0], pattern[0]) and _match(parts[1:], pattern[1:])


#: Files no agent may change, whatever any rule says.
PROTECTED_NAMES: frozenset[str] = frozenset({"context.yaml", ".env", ".git", ".specweaver"})
#: The rules every project starts from; a project's own `[docs]` rules come after them.
_BUILT_IN_RULES = (
    DocRule(paths=["README.md"], access="human"),
    DocRule(paths=["docs/**"], access="human"),
)

DocAccess = Literal["keep", "refuse", "task"]


def doc_access(policy: DocPolicy, path: str, step: str | None) -> DocAccess:
    """Whether `step` may change the repo-relative `path`: `keep`, `refuse`, or `task` when no rule
    names it and the task's own list decides.

    The built-in rules come first, then the project's; the last matching rule decides, as in
    `.gitignore`. Case-blind, as a case-insensitive disk is.
    """
    lowered = path.replace("\\", "/").lower()
    if any(part in PROTECTED_NAMES for part in lowered.split("/")):
        return "refuse"
    for rule in reversed((*_BUILT_IN_RULES, *policy.rule)):
        if path_allowed(lowered, [pattern.lower() for pattern in rule.paths]):
            if rule.access == "open" or (rule.access == "step" and step in rule.steps):
                return "keep"
            return "refuse"
    return "task"


def merge_keeps(path: str, allowed: list[str]) -> bool:
    """Whether a task's change to `path` survives the worktree merge — and so may be written.

    Proposed doc changes (`doc_updates.md`) always survive; `README.md` and `docs/` never do.
    """
    lowered = path.lower()  # case-blind, as a case-insensitive disk is
    if lowered.endswith("doc_updates.md"):
        return True
    if lowered == "readme.md" or lowered.startswith("docs/"):
        return False
    return path_allowed(path, allowed)


_MODE_PRIORITY = {AccessMode.READ: 0, AccessMode.WRITE: 1, AccessMode.FULL: 2}


def normalize_grant_path(path: str) -> str:
    """Normalise a path for grant matching: forward slashes, `..` resolved, `.` as empty.

    Resolving `..` is the security half: without it `src/billing/../../shared/secret.py` would be
    judged by its first segments.
    """
    normalized = posixpath.normpath(path.replace("\\", "/"))
    return "" if normalized == "." else normalized


def grant_mode_for(
    normalized_path: str, grants: Sequence[FolderGrant | TaskGrant], cwd: Path
) -> AccessMode | None:
    """The most permissive grant covering `normalized_path`, or None when no grant covers it.

    Grants from the dispatcher are absolute, while tools are told to send paths relative to the
    project root, so a relative path is also tried resolved against `cwd`. A tool that skipped
    that step matched nothing at all.
    """
    cwd_str = str(cwd).replace("\\", "/")
    check_path = normalized_path
    if normalized_path and not os.path.isabs(normalized_path):
        # Normalised AFTER joining: `root/../x` must be judged as `parent/x`, not as text that
        # starts with `root/`. Otherwise a grant on the root covers every path beside it.
        check_path = posixpath.normpath(f"{cwd_str}/{normalized_path}")
    elif not normalized_path:
        check_path = cwd_str

    best: AccessMode | None = None
    for grant in grants:
        if isinstance(grant, TaskGrant):
            covered = grant.covers(check_path)
        else:
            grant_path = grant.path.replace("\\", "/").rstrip("/")
            covered = _path_under_grant(normalized_path, grant_path, grant.recursive) or (
                _path_under_grant(check_path, grant_path, grant.recursive)
            )
        if covered and (best is None or _MODE_PRIORITY[grant.mode] > _MODE_PRIORITY[best]):
            best = grant.mode
    return best


def _path_under_grant(target: str, grant_path: str, recursive: bool) -> bool:
    """Whether `target` falls under a grant: the folder itself, a direct child, or any descendant.

    For `src/domain/billing/calc.py`: grant `src/domain/billing` matches either way; grant
    `src/domain` matches only when recursive.
    """
    target_parts = target.replace("\\", "/").split("/")
    grant_parts = grant_path.split("/")
    if len(target_parts) < len(grant_parts):
        return False
    if any(target_parts[i] != part for i, part in enumerate(grant_parts)):
        return False
    return recursive or len(target_parts) - len(grant_parts) <= 1
