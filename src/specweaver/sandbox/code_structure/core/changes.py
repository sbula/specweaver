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
from specweaver.workspace.ast.refactor.rename import RenamePlan, RenameRefusal, plan_rename

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.sandbox.filesystem.core.executor import FileExecutor
    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface

__all__ = ["Applied", "Sources", "apply_changes", "plan_rename", "project_sources", "rename_plan"]

CODE_SUFFIXES = (".py", ".pyi")
TEXT_SUFFIXES = (".md", ".rst", ".txt", ".yaml", ".yml", ".toml", ".json", ".cfg", ".ini")

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
    sources = project_sources(executor, exclude_dirs, exclude_patterns)
    if sources.unreadable:
        return RenameRefusal(f"could not read {', '.join(sources.unreadable)}"), sources
    return plan_rename(sources.files, str(path), str(symbol), str(new), parser), sources


def apply_changes(
    executor: FileExecutor, original: Mapping[str, str], changes: Mapping[str, str]
) -> Applied:
    """Write `changes`, all or none. `original` is what each file held when the plan was made."""
    protected = [p for p in sorted(changes) if executor.is_protected(p)]
    if protected:
        return Applied(
            False, f"protected file(s) in the change: {', '.join(protected)}; nothing was written"
        )
    stale = [
        p for p in sorted(changes) if executor.read(p, max_bytes=_MAX_BYTES).data != original[p]
    ]
    if stale:
        return Applied(False, f"changed since it was read: {', '.join(stale)}; nothing was written")
    return _write_all(executor, original, changes)


def _write_all(
    executor: FileExecutor, original: Mapping[str, str], changes: Mapping[str, str]
) -> Applied:
    written: list[str] = []
    for path in sorted(changes):
        result = executor.write(path, changes[path])
        if result.status != "success":
            unrestored = [p for p in written if executor.write(p, original[p]).status != "success"]
            note = (
                f"; could not restore {', '.join(unrestored)}"
                if unrestored
                else "; the others were restored"
            )
            return Applied(False, f"writing {path} failed: {result.error}{note}", unrestored)
        written.append(path)
    return Applied(True, f"changed {len(written)} file(s)")
