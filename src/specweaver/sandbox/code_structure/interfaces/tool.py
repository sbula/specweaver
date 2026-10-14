# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CodeStructureTool — agent-facing, role-gated AST execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.code_structure.core import changes
from specweaver.sandbox.security import (
    MODE_ALLOWS_CREATE,
    MODE_ALLOWS_DELETE,
    MODE_ALLOWS_READ,
    MODE_ALLOWS_WRITE,
    AccessMode,
    FolderGrant,
    grant_mode_for,
    normalize_grant_path,
)
from specweaver.workspace.ast.refactor.rename import RenameRefusal, listing

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.models import ToolDefinition
    from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom
    from specweaver.sandbox.filesystem.core.executor import FileExecutor
    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface
    from specweaver.workspace.ast.refactor.rename import Spot

# ---------------------------------------------------------------------------
# Role → allowed intents
# ---------------------------------------------------------------------------

ROLE_INTENTS: dict[str, frozenset[str]] = {
    "implementer": frozenset(
        {
            "read_file_structure",
            "read_symbol",
            "read_symbol_body",
            "read_unrolled_symbol",
            "list_symbols",
            "replace_symbol",
            "replace_symbol_body",
            "delete_symbol",
            "add_symbol",
            "rename_symbol",
            "move_module",
        }
    ),
    "reviewer": frozenset(
        {
            "read_file_structure",
            "read_symbol",
            "read_symbol_body",
            "read_unrolled_symbol",
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


class CodeStructureTool(BaseTool):
    """Agent-facing AST extraction with role-based internet gating and folder grants.

    Args:
        atom: The CodeStructureAtom instance.
        role: The agent's role (determines which intents are allowed).
        grants: List of FolderGrants limiting what paths the LLM can query.
    """

    def __init__(
        self,
        atom: CodeStructureAtom,
        role: str,
        grants: list[FolderGrant],
        hidden_intents: list[str] | None = None,
        executor: FileExecutor | None = None,
        exclude_dirs: set[str] | None = None,
        exclude_patterns: set[str] | None = None,
    ) -> None:
        if role not in ROLE_INTENTS:
            msg = f"Unknown role: {role!r}. Known roles: {sorted(ROLE_INTENTS)}"
            raise ValueError(msg)
        self._atom = atom
        self._role = role
        self._grants = grants
        self._hidden_intents = hidden_intents or []
        self._executor = executor
        self._exclude_dirs = exclude_dirs or set()
        self._exclude_patterns = exclude_patterns or set()

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

    def list_symbols(
        self, path: str, visibility: list[str] | None = None, decorator_filter: str | None = None
    ) -> ToolResult:
        self._require_intent("list_symbols")
        grant_err = self._check_grant(
            path, frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})
        )
        if grant_err:
            return grant_err

        res = self._atom.run(
            {
                "intent": "list_symbols",
                "path": path,
                "visibility": visibility,
                "decorator_filter": decorator_filter,
            }
        )
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

    def read_unrolled_symbol(self, path: str, symbol_name: str) -> ToolResult:
        self._require_intent("read_unrolled_symbol")
        grant_err = self._check_grant(
            path, frozenset({AccessMode.READ, AccessMode.WRITE, AccessMode.FULL})
        )
        if grant_err:
            return grant_err

        res = self._atom.run(
            {"intent": "read_unrolled_symbol", "path": path, "symbol_name": symbol_name}
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

    def rename_symbol(self, path: str, symbol_name: str, new_name: str) -> ToolResult:
        """Rename a symbol and its proven uses, all files or none, inside the role's grants."""
        self._require_intent("rename_symbol")
        grant_err = self._check_grant(path, MODE_ALLOWS_WRITE)
        if grant_err:
            return grant_err
        parser = _parser_for(path)
        if self._executor is None or parser is None:
            return ToolResult(status="error", message=f"rename is not supported for {path}")
        context = {"path": path, "symbol_name": symbol_name, "new_name": new_name}
        plan, sources = changes.rename_plan(
            self._executor, parser, context, self._exclude_dirs, self._exclude_patterns
        )
        if isinstance(plan, RenameRefusal):
            return ToolResult(status="error", message=self._refusal_text(plan.reason, plan.spots))
        outside = [p for p in plan.changes if self._mode_of(p) not in MODE_ALLOWS_WRITE]
        if outside:
            return ToolResult(
                status="error",
                message=f"{len(outside)} file(s) of the rename are outside your write grants; "
                "nothing was changed",
            )
        applied = changes.apply_changes(self._executor, sources.files, plan.changes)
        if not applied.ok:
            return ToolResult(status="error", message=applied.message)
        seen, hidden = self._readable(plan.mentions)
        return ToolResult(
            status="success",
            message=f"Renamed '{symbol_name}' to '{new_name}': {applied.message}",
            data={
                "changed": sorted(plan.changes),
                "mentions": [str(s) for s in seen],
                "mentions_outside_grants": hidden,
            },
        )

    def move_module(self, path: str, new_path: str) -> ToolResult:
        """Move a file and rewrite its imports, all files or none, inside the role's grants."""
        self._require_intent("move_module")
        if self._mode_of(path) not in MODE_ALLOWS_DELETE:
            return ToolResult(status="error", message=f"moving needs the right to delete {path}")
        if self._mode_of(new_path) not in MODE_ALLOWS_CREATE:
            return ToolResult(
                status="error", message=f"moving needs the right to create {new_path}"
            )
        parser = _parser_for(path)
        if self._executor is None or parser is None:
            return ToolResult(status="error", message=f"moving is not supported for {path}")
        context = {"path": path, "new_path": new_path}
        plan, sources = changes.move_plan(
            self._executor, parser, context, self._exclude_dirs, self._exclude_patterns
        )
        if isinstance(plan, RenameRefusal):
            return ToolResult(status="error", message=self._refusal_text(plan.reason, plan.spots))
        others = [p for p in plan.changes if p != plan.new_path]
        outside = [p for p in others if self._mode_of(p) not in MODE_ALLOWS_WRITE]
        if outside:
            return ToolResult(
                status="error",
                message=f"{len(outside)} file(s) of the move are outside your write grants; nothing was changed",
            )
        applied = changes.apply_changes(self._executor, sources.files, plan.changes, plan.old_path)
        if not applied.ok:
            return ToolResult(status="error", message=applied.message)
        seen, hidden = self._readable(plan.mentions)
        return ToolResult(
            status="success",
            message=f"Moved {path} to {plan.new_path}: {applied.message}",
            data={
                "moved": [path, plan.new_path],
                "changed": sorted(plan.changes),
                "mentions": [str(s) for s in seen],
                "mentions_outside_grants": hidden,
            },
        )

    def _mode_of(self, path: str) -> AccessMode | None:
        return self._resolve_mode(self._normalize_path(path))

    def _readable(self, spots: list[Spot]) -> tuple[list[Spot], int]:
        """The spots the role may read, and how many others there are."""
        seen = [s for s in spots if self._mode_of(s.path) in MODE_ALLOWS_READ]
        return seen, len(spots) - len(seen)

    def _refusal_text(self, reason: str, spots: list[Spot]) -> str:
        seen, hidden = self._readable(spots)
        text = f"{reason}: {listing(seen)}" if seen else reason
        return f"{text}; {hidden} in files outside your read grants" if hidden else text

    def definitions(self) -> list[ToolDefinition]:
        from specweaver.sandbox.code_structure.interfaces.definitions import (
            get_code_structure_schema,
        )

        supported_intents, supported_params_flat = self._atom.get_supported_capabilities()

        supported_params = {"list_symbols": supported_params_flat}

        all_defs = get_code_structure_schema(supported_intents, supported_params)
        allowed = ROLE_INTENTS[self._role]
        return [d for d in all_defs if d.name in allowed and d.name not in self._hidden_intents]

    def _require_intent(self, intent: str) -> None:
        if intent not in ROLE_INTENTS[self._role]:
            msg = (
                f"Intent {intent!r} is not allowed for role {self._role!r}. "
                f"Allowed: {sorted(ROLE_INTENTS[self._role])}"
            )
            raise CodeStructureToolError(msg)

    # -------------------------------------------------------------------
    # Internal: boundary enforcement — the shared matcher in `sandbox.security`
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_path(path: str) -> str:
        return normalize_grant_path(path)

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
        return grant_mode_for(normalized_path, self._grants, self._atom.cwd)


def _parser_for(path: str) -> CodeStructureInterface | None:
    from pathlib import PurePosixPath

    from specweaver.workspace.ast.parsers.factory import get_default_parsers

    suffix = PurePosixPath(path).suffix.lower()
    return next((p for exts, p in get_default_parsers().items() if suffix in exts), None)
