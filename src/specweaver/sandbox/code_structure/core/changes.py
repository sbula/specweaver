# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Read a project's files and write a change to several of them: all files, or none.

The Tool and the Atom both use these. Everything goes through the `FileExecutor`, so its path,
symlink and protected-file checks hold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from specweaver.workspace.ast.parsers.exclusions import SpecWeaverIgnoreParser
from specweaver.workspace.ast.refactor.move import MovePlan, plan_move
from specweaver.workspace.ast.refactor.rename import (
    CODE_SUFFIXES,
    RenamePlan,
    RenameRefusal,
    Spot,
    family_of,
    plan_rename,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.sandbox.filesystem.core.executor import FileExecutor
    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface

__all__ = [
    "Applied",
    "Sources",
    "apply_changes",
    "move_plan",
    "plan_move",
    "plan_rename",
    "project_sources",
    "rename_plan",
]

TEXT_SUFFIXES = (".md", ".rst", ".txt", ".yaml", ".yml", ".toml", ".json", ".cfg", ".ini", ".mod")

#: Folders no project scan enters, whatever the exclusions say.
_ALWAYS_SKIPPED = frozenset(
    {".git", ".specweaver", ".worktrees", ".venv", "venv", "__pycache__", "node_modules"}
)
_MAX_BYTES = 2 * 1024 * 1024


@dataclass
class Sources:
    """The project's files by path, and the code files that could not be read."""

    files: dict[str, str] = field(default_factory=dict)
    unreadable: list[str] = field(default_factory=list)


@dataclass
class Applied:
    """What writing a change did."""

    ok: bool
    message: str
    unrestored: list[str] = field(default_factory=list)


class _IgnoreFile:
    """`.specweaverignore`, read through the executor."""

    def __init__(self, executor: FileExecutor) -> None:
        self._read = executor.read(".specweaverignore")

    def exists(self) -> bool:
        return self._read.status == "success"

    def is_file(self) -> bool:
        return self.exists()

    def read_text(self) -> str:
        return str(self._read.data)

    def append_lines(self, lines: list[str]) -> None:
        raise NotImplementedError("a scan never writes the ignore file")


def project_sources(
    executor: FileExecutor,
    exclude_dirs: set[str] | None = None,
    exclude_patterns: set[str] | None = None,
) -> Sources:
    """Every code and text file under the root, skipping links, ignored and excluded paths."""
    skipped = _ALWAYS_SKIPPED | (exclude_dirs or set())
    runtime = sorted(exclude_patterns or set()) + [f"{d}/" for d in sorted(exclude_dirs or set())]
    ignored = SpecWeaverIgnoreParser(_IgnoreFile(executor)).get_compiled_spec(runtime)
    found = Sources()
    todo = [""]
    while todo:
        for rel, kind in _entries(executor, todo.pop(), ignored):
            if kind == "dir" and rel.rsplit("/", 1)[-1] not in skipped:
                todo.append(rel)
            elif kind == "file" and rel.endswith(CODE_SUFFIXES + TEXT_SUFFIXES):
                _read_into(executor, rel, found)
    return found


def _entries(executor: FileExecutor, directory: str, ignored: Any) -> list[tuple[str, str]]:
    """`(path, kind)` of each entry of `directory` that is not ignored. A link is never read."""
    listed = executor.dir_kinds(directory)
    entries = []
    for name, kind in listed.data if listed.status == "success" else []:
        rel = f"{directory}/{name}" if directory else name
        if not ignored.match_file(rel + ("/" if kind == "dir" else "")):
            entries.append((rel, kind))
    return entries


def _read_into(executor: FileExecutor, rel: str, found: Sources) -> None:
    read = executor.read(rel, max_bytes=_MAX_BYTES)
    if read.status == "success":
        found.files[rel] = str(read.data)
    elif rel.endswith(CODE_SUFFIXES):
        found.unreadable.append(rel)


def _read_project(
    executor: FileExecutor,
    path: str,
    exclude_dirs: set[str] | None,
    exclude_patterns: set[str] | None,
) -> Sources | RenameRefusal:
    """The project's files, or a refusal when a code file of `path`'s language cannot be read."""
    sources = project_sources(executor, exclude_dirs, exclude_patterns)
    unreadable = [p for p in sources.unreadable if p.endswith(family_of(path))]
    if unreadable:
        spots = [Spot(p, 1) for p in unreadable]
        return RenameRefusal(f"could not read {len(spots)} code file(s)", spots)
    return sources


def rename_plan(
    executor: FileExecutor,
    parser: CodeStructureInterface,
    context: Mapping[str, object],
    exclude_dirs: set[str] | None = None,
    exclude_patterns: set[str] | None = None,
) -> tuple[RenamePlan | RenameRefusal, Sources]:
    """Read the project and plan `context`'s rename: `path`, `symbol_name`, `new_name`."""
    path, symbol, new = (context.get(k) for k in ("path", "symbol_name", "new_name"))
    if not all(isinstance(v, str) and v for v in (path, symbol, new)):
        return RenameRefusal("rename needs 'path', 'symbol_name' and 'new_name'"), Sources()
    sources = _read_project(executor, str(path), exclude_dirs, exclude_patterns)
    if isinstance(sources, RenameRefusal):
        return sources, Sources()
    return plan_rename(sources.files, str(path), str(symbol), str(new), parser), sources


def move_plan(
    executor: FileExecutor,
    parser: CodeStructureInterface,
    context: Mapping[str, object],
    exclude_dirs: set[str] | None = None,
    exclude_patterns: set[str] | None = None,
) -> tuple[MovePlan | RenameRefusal, Sources]:
    """Read the project and plan `context`'s move: `path` to `new_path`."""
    path, new_path = context.get("path"), context.get("new_path")
    if not all(isinstance(v, str) and v for v in (path, new_path)):
        return RenameRefusal("a move needs 'path' and 'new_path'"), Sources()
    sources = _read_project(executor, str(path), exclude_dirs, exclude_patterns)
    if isinstance(sources, RenameRefusal):
        return sources, Sources()
    return plan_move(sources.files, str(path), str(new_path), parser), sources


def apply_changes(
    executor: FileExecutor,
    original: Mapping[str, str],
    changes: Mapping[str, str],
    delete: str | None = None,
) -> Applied:
    """Write `changes` and delete `delete`, all or none.

    `original` is what each file held when the plan was made; a changed path missing from it is
    a new file, and must not exist yet.
    """
    touched = sorted({*changes, *([delete] if delete else [])})
    protected = [p for p in touched if executor.is_protected(p)]
    if protected:
        return Applied(
            False, f"protected file(s) in the change: {', '.join(protected)}; nothing was written"
        )
    created = [p for p in sorted(changes) if p not in original and executor.exists(p).data]
    if created:
        return Applied(False, f"{', '.join(created)} exists already; nothing was written")
    stale = [
        p
        for p in touched
        if p in original and executor.read(p, max_bytes=_MAX_BYTES).data != original[p]
    ]
    if stale:
        return Applied(False, f"changed since it was read: {', '.join(stale)}; nothing was written")
    return _write_all(executor, original, changes, delete)


def _undo(executor: FileExecutor, original: Mapping[str, str], written: list[str]) -> list[str]:
    """Put every written file back; a new one is removed. The files that could not be undone."""
    failed = []
    for p in written:
        result = executor.write(p, original[p]) if p in original else executor.delete(p)
        if result.status != "success":
            failed.append(p)
    return failed


def _write_all(
    executor: FileExecutor,
    original: Mapping[str, str],
    changes: Mapping[str, str],
    delete: str | None,
) -> Applied:
    written: list[str] = []
    for path in sorted(changes):
        result = executor.write(path, changes[path])
        if result.status != "success":
            return _failed(executor, original, written, f"writing {path} failed: {result.error}")
        written.append(path)
    if delete:
        result = executor.delete(delete)
        if result.status != "success":
            return _failed(executor, original, written, f"deleting {delete} failed: {result.error}")
    return Applied(True, f"changed {len(written)} file(s)")


def _failed(
    executor: FileExecutor, original: Mapping[str, str], written: list[str], why: str
) -> Applied:
    unrestored = _undo(executor, original, written)
    note = (
        f"; could not restore {', '.join(unrestored)}"
        if unrestored
        else "; the others were restored"
    )
    return Applied(False, f"{why}{note}", unrestored)
