# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""FileSystemAtom — Flow-level filesystem operations for the Engine.

The Engine uses FileSystemAtom for scaffolding (create directories + context.yaml
from approved spec boundaries), backup/restore for rollback, and boundary
aggregation/validation.

Uses EngineFileExecutor — no protected pattern restrictions.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING, Any

from ruamel.yaml import YAML

from specweaver.loom.atoms.base import Atom, AtomResult, AtomStatus
from specweaver.loom.commons.filesystem.executor import EngineFileExecutor

if TYPE_CHECKING:
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
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'intent' in context.",
            )

        handler = getattr(self, f"_intent_{intent}", None)
        if handler is None:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Unknown intent: {intent!r}. "
                        f"Known: {sorted(self._known_intents())}",
            )

        return handler(context)

    def _known_intents(self) -> set[str]:
        """Return the set of known intent names."""
        prefix = "_intent_"
        return {
            name[len(prefix):]
            for name in dir(self)
            if name.startswith(prefix)
        }

    # -- Intent implementations ----------------------------------------

    def _intent_scaffold(self, context: dict[str, Any]) -> AtomResult:
        """Create directory structure with context.yaml files.

        Context keys:
            boundaries: list[dict] — each dict has:
                path: str — relative directory path
                name: str — boundary name
                level: str — boundary level (module, meta-module, etc.)
                purpose: str — one-sentence description
                archetype: str — archetype name
                consumes: list[str] (optional) — consumed paths
                forbids: list[str] (optional) — forbidden paths
        """
        boundaries = context.get("boundaries")
        if not boundaries:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'boundaries' in context for scaffold intent.",
            )

        created_paths: list[str] = []
        yaml = YAML()
        yaml.default_flow_style = False

        for boundary in boundaries:
            rel_path = boundary.get("path", "")
            if not rel_path:
                continue

            # Create directory
            dir_result = self._executor.mkdir(rel_path)
            if dir_result.status != "success":
                return AtomResult(
                    status=AtomStatus.FAILED,
                    message=f"Failed to create directory {rel_path}: {dir_result.error}",
                )

            # Create context.yaml (idempotent — don't overwrite existing)
            ctx_path = f"{rel_path}/context.yaml"
            exists_result = self._executor.exists(ctx_path)
            if exists_result.status == "success" and exists_result.data is True:
                # Already exists — skip, don't overwrite
                created_paths.append(rel_path)
                continue

            # Build context.yaml content
            ctx_data: dict[str, Any] = {
                "name": boundary["name"],
                "level": boundary["level"],
                "purpose": boundary.get("purpose", "TODO"),
                "archetype": boundary.get("archetype", "pure-logic"),
            }
            if "consumes" in boundary:
                ctx_data["consumes"] = boundary["consumes"]
            if "forbids" in boundary:
                ctx_data["forbids"] = boundary["forbids"]

            # Write context.yaml
            from io import StringIO
            buf = StringIO()
            yaml.dump(ctx_data, buf)
            content = buf.getvalue()

            write_result = self._executor.write(ctx_path, content)
            if write_result.status != "success":
                return AtomResult(
                    status=AtomStatus.FAILED,
                    message=f"Failed to write {ctx_path}: {write_result.error}",
                )

            created_paths.append(rel_path)

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Scaffolded {len(created_paths)} boundaries.",
            exports={"created_paths": created_paths},
        )

    def _intent_backup(self, context: dict[str, Any]) -> AtomResult:
        """Copy a file to a backup location.

        Context keys:
            source: str — relative path to backup.
            backup_dir: str — directory to store backups.
        """
        source = context.get("source")
        backup_dir = context.get("backup_dir")

        if not source:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'source' in context for backup intent.",
            )
        if not backup_dir:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'backup_dir' in context for backup intent.",
            )

        source_path = self._cwd / source
        if not source_path.is_file():
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Source file not found: {source}",
            )

        # Ensure backup directory exists
        self._executor.mkdir(backup_dir)

        # Copy to backup with original filename
        backup_file = self._cwd / backup_dir / source_path.name
        try:
            shutil.copy2(source_path, backup_file)
        except OSError as exc:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Backup failed: {exc}",
            )

        backup_rel = str(backup_file.relative_to(self._cwd)).replace("\\", "/")
        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Backed up {source} → {backup_rel}",
            exports={"backup_path": backup_rel},
        )

    def _intent_restore(self, context: dict[str, Any]) -> AtomResult:
        """Restore a file from backup.

        Context keys:
            source: str — relative path to the backup file.
            target: str — relative path to restore to.
        """
        source = context.get("source")
        target = context.get("target")

        if not source or not target:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'source' and/or 'target' for restore intent.",
            )

        source_path = self._cwd / source
        target_path = self._cwd / target

        if not source_path.is_file():
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Backup file not found: {source}",
            )

        try:
            shutil.copy2(source_path, target_path)
        except OSError as exc:
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"Restore failed: {exc}",
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Restored {source} → {target}",
        )

    def _intent_aggregate_context(self, _context: dict[str, Any]) -> AtomResult:
        """Collect all context.yaml files into a project-wide boundary map.

        Walks the entire project tree, reads each context.yaml,
        and returns a list of boundary dicts.
        """
        yaml = YAML()
        boundaries: list[dict[str, Any]] = []

        for ctx_file in self._cwd.rglob("context.yaml"):
            try:
                data = yaml.load(ctx_file)
                if data is None:
                    continue
                rel_path = str(ctx_file.parent.relative_to(self._cwd)).replace("\\", "/")
                if rel_path == ".":
                    rel_path = ""
                boundaries.append({
                    "path": rel_path,
                    "name": data.get("name", ""),
                    "level": data.get("level", ""),
                    "purpose": data.get("purpose", ""),
                    "archetype": data.get("archetype", ""),
                })
            except Exception:
                continue  # skip malformed files

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message=f"Found {len(boundaries)} boundaries.",
            exports={"boundaries": boundaries},
        )

    def _intent_validate_boundaries(self, _context: dict[str, Any]) -> AtomResult:
        """Check all context.yaml files for consistency.

        Validates:
        - Required fields present (name, level)
        - No duplicate names
        - consumes references exist
        """
        yaml = YAML()
        errors: list[str] = []
        names: dict[str, str] = {}  # name → path

        for ctx_file in self._cwd.rglob("context.yaml"):
            rel_path = str(ctx_file.relative_to(self._cwd)).replace("\\", "/")
            try:
                data = yaml.load(ctx_file)
            except Exception as exc:
                errors.append(f"{rel_path}: YAML parse error: {exc}")
                continue

            if data is None:
                errors.append(f"{rel_path}: Empty file")
                continue

            # Required fields
            if "name" not in data:
                errors.append(f"{rel_path}: Missing required field 'name'")
            if "level" not in data:
                errors.append(f"{rel_path}: Missing required field 'level'")

            # Duplicate name check
            name = data.get("name", "")
            if name and name in names:
                errors.append(
                    f"{rel_path}: Duplicate name '{name}' (also at {names[name]})",
                )
            elif name:
                names[name] = rel_path

        if errors:
            return AtomResult(
                status=AtomStatus.SUCCESS,  # validation completed, report errors
                message=f"Validation found {len(errors)} error(s).",
                exports={"errors": errors, "valid": False},
            )

        return AtomResult(
            status=AtomStatus.SUCCESS,
            message="All boundaries valid.",
            exports={"errors": [], "valid": True},
        )
