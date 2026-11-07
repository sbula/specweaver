# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file's schema version in `PRAGMA user_version`, and the steps that bring it up to date.

Each step and its version change commit in one `BEGIN IMMEDIATE` transaction, and the version is
read again once the lock is held, so two processes starting together never apply a step twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.infrastructure.database.sqlite import open_sqlite

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Callable, Sequence

_UPGRADED: set[str] = set()


@dataclass(frozen=True)
class Step:
    """One schema change; `version` is the file's version once it has run."""

    version: int
    name: str
    apply: Callable[[sqlite3.Connection], None]


class SchemaTooNewError(RuntimeError):
    """The file was written by a newer SpecWeaver than this one."""

    def __init__(self, path: Path, found: int, known: int) -> None:
        super().__init__(
            f"{path} is at schema version {found}, but this SpecWeaver knows only up to {known}; "
            f"update SpecWeaver to open it"
        )


class SchemaStepError(RuntimeError):
    """A schema step failed; the file is still at the version before it."""

    def __init__(self, path: Path, step: str, cause: BaseException) -> None:
        super().__init__(f"{path}: the schema step '{step}' failed and was undone: {cause}")


def _version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _check_order(steps: Sequence[Step]) -> None:
    versions = [step.version for step in steps]
    if versions != list(range(1, len(steps) + 1)):
        raise ValueError(f"schema steps must be numbered 1, 2, 3 … in order, not {versions}")


def _run(
    conn: sqlite3.Connection,
    path: Path,
    step: Step,
    adopt: Callable[[sqlite3.Connection], None] | None,
) -> None:
    conn.execute("BEGIN IMMEDIATE")
    try:
        if adopt is not None:
            adopt(conn)
        if _version(conn) < step.version:
            step.apply(conn)
            conn.execute(f"PRAGMA user_version = {step.version}")
        conn.execute("COMMIT")
    except Exception as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise SchemaStepError(path, step.name, exc) from exc


def upgrade(
    path: Path | str,
    steps: Sequence[Step],
    *,
    adopt: Callable[[sqlite3.Connection], None] | None = None,
    _seen: set[str] | None = None,
) -> None:
    """Run the steps `path` lacks, once per process.

    `adopt` runs inside the first missing step's transaction, before it: an old file's own version
    record is read there and turned into `user_version`.
    """
    seen = _UPGRADED if _seen is None else _seen
    path = Path(path)
    key = str(path.resolve())
    if key in seen:
        return
    _check_order(steps)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = open_sqlite(path, isolation_level=None)
    try:
        known = len(steps)
        found = _version(conn)
        if found > known:
            raise SchemaTooNewError(path, found, known)
        for step in steps:
            if _version(conn) < step.version:
                _run(conn, path, step, adopt)
                adopt = None
    finally:
        conn.close()
    seen.add(key)
