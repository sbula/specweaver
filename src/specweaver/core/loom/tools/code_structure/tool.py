# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CodeStructureTool — agent-facing, role-gated AST execution."""

from __future__ import annotations

import logging
import os
import posixpath
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from specweaver.core.loom.security import AccessMode, FolderGrant

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom

# ---------------------------------------------------------------------------
# Role → allowed intents
# ---------------------------------------------------------------------------

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset(
        {
            "read_file_structure",
            "read_symbol",
            "read_symbol_body",
            "list_symbols",
            "replace_symbol",
            "replace_symbol_body",
            "delete_symbol",
            "add_symbol",
        }
    ),
    "reviewer": frozenset(
        {
            "read_file_structure",
            "read_symbol",
            "read_symbol_body",
            "list_symbols",
        }
    ),
    "planner": frozenset(
        {
            "read_file_structure",
            "list_symbols",
        }
    ),
    "drafter": frozenset(
        {
            "read_file_structure",
        }
    ),
}


@dataclass(frozen=True)
class ToolResult:
    """Result from a CodeStructureTool operation."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


class CodeStructureToolError(Exception):
    """Raised when an operation is blocked by role or config."""


class CodeStructureTool:
    """Agent-facing AST extraction with role-based internet gating and folder grants.

    Args:
        atom: The CodeStructureAtom instance.
        role: The agent's role (determines which intents are allowed).
        grants: List of FolderGrants limiting what paths the LLM can query.
    """

    def __init__(self, atom: CodeStructureAtom, role: str, grants: list[FolderGrant]) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._atom = atom
        self._role = role
        self._grants = grants

    @property
    def role(self) -> str:
        return self._role

    def read_file_structure(self, path: str) -> ToolResult:
        self._require_intent("read_file_structure")
        grant_err = self._check_grant(
            path, frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})
        )
        if grant_err:
            return grant_err

        res = self._atom.run({"intent": "read_file_structure", "path": path})
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def list_symbols(self, path: str, visibility: list[str] | None = None) -> ToolResult:
        self._require_intent("list_symbols")
        grant_err = self._check_grant(
            path, frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})
        )
        if grant_err:
            return grant_err

        res = self._atom.run({"intent": "list_symbols", "path": path, "visibility": visibility})
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def read_symbol(self, path: str, symbol_name: str) -> ToolResult:
        self._require_intent("read_symbol")
        grant_err = self._check_grant(
            path, frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})
        )
        if grant_err:
            return grant_err

        res = self._atom.run({"intent": "read_symbol", "path": path, "symbol_name": symbol_name})
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def read_symbol_body(self, path: str, symbol_name: str) -> ToolResult:
        self._require_intent("read_symbol_body")
        grant_err = self._check_grant(
            path, frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})
        )
        if grant_err:
            return grant_err

        res = self._atom.run(
            {"intent": "read_symbol_body", "path": path, "symbol_name": symbol_name}
        )
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def replace_symbol(self, path: str, symbol_name: str, new_code: str) -> ToolResult:
        self._require_intent("replace_symbol")
        grant_err = self._check_grant(path, frozenset({AccessMode.WRITE, AccessMode.FULL}))
        if grant_err:
            return grant_err

        res = self._atom.run(
            {
                "intent": "replace_symbol",
                "path": path,
                "symbol_name": symbol_name,
                "new_code": new_code,
            }
        )
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def replace_symbol_body(self, path: str, symbol_name: str, new_code: str) -> ToolResult:
        self._require_intent("replace_symbol_body")
        grant_err = self._check_grant(path, frozenset({AccessMode.WRITE, AccessMode.FULL}))
        if grant_err:
            return grant_err

        res = self._atom.run(
            {
                "intent": "replace_symbol_body",
                "path": path,
                "symbol_name": symbol_name,
                "new_code": new_code,
            }
        )
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def delete_symbol(self, path: str, symbol_name: str) -> ToolResult:
        self._require_intent("delete_symbol")
        grant_err = self._check_grant(path, frozenset({AccessMode.WRITE, AccessMode.FULL}))
        if grant_err:
            return grant_err

        res = self._atom.run({"intent": "delete_symbol", "path": path, "symbol_name": symbol_name})
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def add_symbol(self, path: str, new_code: str, target_parent: str | None = None) -> ToolResult:
        self._require_intent("add_symbol")
        grant_err = self._check_grant(path, frozenset({AccessMode.WRITE, AccessMode.FULL}))
        if grant_err:
            return grant_err

        res = self._atom.run(
            {
                "intent": "add_symbol",
                "path": path,
                "new_code": new_code,
                "target_parent": target_parent,
            }
        )
        return ToolResult(
            status="success" if res.status.value == "SUCCESS" else "error",
            message=res.message,
            data=res.exports,
        )

    def definitions(self) -> list[Any]:
        from specweaver.core.loom.tools.code_structure.definitions import get_code_structure_schema

        all_defs = get_code_structure_schema()
        allowed = ROLE_INTENTS[self._role]
        return [d for d in all_defs if d.name in allowed]

    def _require_intent(self, intent: str) -> None:
        if intent not in ROLE_INTENTS[self._role]:
            msg = (
                f"Intent {intent!r} is not allowed for role {self._role!r}. "
                f"Allowed: {sorted(ROLE_INTENTS[self._role])}"
            )
            raise CodeStructureToolError(msg)

    # -------------------------------------------------------------------
    # Internal: boundary enforcement (identical to FileSystemTool logic)
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_path(path: str) -> str:
        forward = path.replace("\\", "/")
        normalized = posixpath.normpath(forward)
        if normalized == ".":
            return ""
        return normalized

    def _check_grant(self, path: str, required_modes: frozenset[AccessMode]) -> ToolResult | None:
        normalized = self._normalize_path(path)
        best_mode = self._resolve_mode(normalized)

        if best_mode is None:
            return ToolResult(status="error", message=f"No grant covers path: {path}")

        if best_mode not in required_modes:
            return ToolResult(
                status="error", message=f"Insufficient permissions ({best_mode}) for path: {path}"
            )

        return None

    def _resolve_mode(self, normalized_path: str) -> AccessMode | None:
        mode_priority = {AccessMode.READ: 0, AccessMode.WRITE: 1, AccessMode.FULL: 2}
        best: AccessMode | None = None

        check_path = normalized_path
        if normalized_path and not os.path.isabs(normalized_path):
            check_path = f"/{normalized_path}"
        elif not normalized_path:
            check_path = "/"

        for grant in self._grants:
            grant_path = grant.path.replace("\\", "/").rstrip("/")
            if grant_path and not os.path.isabs(grant_path):
                grant_path = f"/{grant_path}"
            if not grant_path:
                grant_path = "/"

            if (
                self._path_matches_grant(
                    normalized_path, grant.path.replace("\\", "/").rstrip("/"), grant.recursive
                )
                or self._path_matches_grant(check_path, grant_path, grant.recursive)
            ) and (best is None or mode_priority[grant.mode] > mode_priority[best]):
                best = grant.mode

        return best

    def _path_matches_grant(self, target: str, grant_path: str, recursive: bool) -> bool:
        if not target and not grant_path:
            return True
        if target == grant_path:
            return True
        if not grant_path:
            return recursive
        if target.startswith(f"{grant_path}/"):
            if recursive:
                return True
            remainder = target[len(grant_path) + 1 :]
            return "/" not in remainder
        return False
