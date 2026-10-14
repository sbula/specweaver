# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CodeStructureTool — agent-facing, role-gated AST execution."""

from __future__ import annotations

import logging
import typing
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
    from specweaver.workspace.ast.refactor.move import MovePlan
    from specweaver.workspace.ast.refactor.rename import RenamePlan, Spot

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
            "create_module",
            "delete_module",
            "read_symbol_doc",
            "replace_symbol_doc",
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

    def read_symbol_doc(self, path: str, symbol_name: str) -> ToolResult:
        """The doc of one symbol as plain text."""
        self._require_intent("read_symbol_doc")
        grant_err = self._check_grant(path, MODE_ALLOWS_READ)
        if grant_err:
            return grant_err
        return self._run({"intent": "read_symbol_doc", "path": path, "symbol_name": symbol_name})

    def replace_symbol_doc(self, path: str, symbol_name: str, doc: str) -> ToolResult:
        """Replace the doc of one symbol with plain `doc`; `""` removes it."""
        self._require_intent("replace_symbol_doc")
        grant_err = self._check_grant(path, MODE_ALLOWS_WRITE)
        if grant_err:
            return grant_err
        return self._run(
            {"intent": "replace_symbol_doc", "path": path, "symbol_name": symbol_name, "doc": doc}
        )

    def _run(self, context: dict[str, str]) -> ToolResult:
        res = self._atom.run(context)
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
        context = {"path": path, "symbol_name": symbol_name, "new_name": new_name}
        planned = self._planned("rename_symbol", path, context)
        if isinstance(planned, ToolResult):
            return planned
        plan, sources = typing.cast("RenamePlan", planned[0]), planned[1]
        return self._apply_edits(
            sources,
            plan,
            list(plan.changes),
            "rename",
            f"Renamed '{symbol_name}' to '{new_name}'",
            {},
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
        context = {"path": path, "new_path": new_path}
        planned = self._planned("move_module", path, context)
        if isinstance(planned, ToolResult):
            return planned
        plan, sources = typing.cast("MovePlan", planned[0]), planned[1]
        others = [p for p in plan.changes if p != plan.new_path]
        return self._apply_edits(
            sources,
            plan,
            others,
            "move",
            f"Moved {path} to {plan.new_path}",
            {"moved": [path, plan.new_path]},
        )

    def create_module(self, path: str, code: str) -> ToolResult:
        """Create a new file holding `code`, where the role may create it."""
        self._require_intent("create_module")
        if self._mode_of(path) not in MODE_ALLOWS_CREATE:
            return ToolResult(status="error", message=f"creating needs the right to create {path}")
        return self._file_change("create_module", {"path": path, "code": code}, path)

    def delete_module(self, path: str) -> ToolResult:
        """Delete a file nothing uses, where the role may delete it."""
        self._require_intent("delete_module")
        if self._mode_of(path) not in MODE_ALLOWS_DELETE:
            return ToolResult(status="error", message=f"deleting needs the right to delete {path}")
        return self._file_change("delete_module", {"path": path}, path)

    def _apply_edits(
        self,
        sources: Any,
        plan: RenamePlan | MovePlan,
        edited: list[str],
        what: str,
        done: str,
        data: dict[str, Any],
    ) -> ToolResult:
        """Write a plan whose `edited` files all need write grants, and report its mentions."""
        outside = [p for p in edited if self._mode_of(p) not in MODE_ALLOWS_WRITE]
        if outside:
            return ToolResult(
                status="error",
                message=f"{len(outside)} file(s) of the {what} are outside your write grants; "
                "nothing was changed",
            )
        applied = self._apply(sources, plan)
        if not applied.ok:
            return ToolResult(status="error", message=applied.message)
        seen, hidden = self._readable(plan.mentions)
        return ToolResult(
            status="success",
            message=f"{done}: {applied.message}",
            data={
                **data,
                "changed": sorted(plan.changes),
                "mentions": [str(s) for s in seen],
                "mentions_outside_grants": hidden,
            },
        )

    def _file_change(self, intent: str, context: dict[str, str], path: str) -> ToolResult:
        planned = self._planned(intent, path, context)
        if isinstance(planned, ToolResult):
            return planned
        plan, sources = planned
        applied = self._apply(sources, plan)
        if not applied.ok:
            return ToolResult(status="error", message=applied.message)
        key = "created" if intent == "create_module" else "deleted"
        return ToolResult(status="success", message=f"{key.capitalize()} {path}", data={key: path})

    def _planned(
        self, intent: str, path: str, context: dict[str, str]
    ) -> ToolResult | tuple[Any, Any]:
        """The plan of a change intent and the files it read, or the error to return."""
        parser = _parser_for(path)
        if self._executor is None or parser is None:
            return ToolResult(status="error", message=f"{intent} is not supported for {path}")
        plan, sources = changes.plan_change(
            intent, self._executor, parser, context, self._exclude_dirs, self._exclude_patterns
        )
        if isinstance(plan, RenameRefusal):
            return ToolResult(status="error", message=self._refusal_text(plan.reason, plan.spots))
        return plan, sources

    def _apply(self, sources: Any, plan: Any) -> changes.Applied:
        if self._executor is None:
            raise CodeStructureToolError("this tool has no executor to write with")
        return changes.apply_plan(self._executor, sources, plan)

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
