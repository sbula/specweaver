# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""AST scanners shared by the architecture test modules.

Lives here rather than inside a test module because two suites need it, and `tests/fixtures/` is
where this repo already puts logic shared between test files (`db_utils.py` is the precedent).
Importing a test module to borrow a helper would execute that module's collection-time code as a
side effect and couple the two suites for no reason.

This module must name no story id. Files under `tests/` that name a story are credited with every
requirement token they contain, so a helper that mentioned one would hand it every id in here.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def import_offenders(root: Path, prefixes: tuple[str, ...], *, recursive: bool) -> list[str]:
    """Absolute imports under `root` whose module path starts with one of `prefixes`.

    Whole-module, not import-time only: an import deferred inside a function is still a
    dependency, and this repo's cycle gate explicitly rejects deferring an import as a way to
    break one.

    Only ABSOLUTE imports are matched. A parent-relative one (`from ...workspace import store`)
    would slip past — and cannot occur: ruff's TID252 bans parent-relative imports repo-wide, and
    a sibling-relative import cannot reach out of a package at all. Verified, not assumed.
    Relaxing TID252 would silently open this hole. A sibling-relative `from . import x` carries no
    module path and is correctly ignored rather than crashing.

    `recursive` is not a convenience flag and the two current callers need opposite values, so it
    is keyword-only and has no default — a caller must state which one it means. `core/config/`
    scans top-level-only *because* `bootstrap/` and `interfaces/` are separately-scoped and allowed
    to reach domains; a layer with no such carve-out must scan its whole tree or it inspects almost
    nothing and passes on an empty set.

    An **empty** `prefixes` reports nothing, because `str.startswith(())` is always False. That is
    inherited behaviour, not a decision, so it is pinned by a test: a caller computing prefixes
    dynamically and arriving at an empty tuple would otherwise get a silent all-clear.

    A module whose SOURCE cannot be parsed raises rather than being skipped — skipping is how an
    absence proof goes quietly vacuous — and the path is added to the message, because a bare
    syntax error sends the reader to the wrong place. That wrapping covers `SyntaxError` only. A
    file that is not valid UTF-8 raises `UnicodeDecodeError` from the read, unwrapped and without
    the path prefix; that is a different problem from a malformed module and is left to surface as
    itself.
    """
    offenders: list[str] = []
    for path in sorted(root.glob("**/*.py" if recursive else "*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            msg = f"{path.name}: cannot parse ({exc})"
            raise SyntaxError(msg) from exc
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            offenders.extend(f"{path.name}: {n}" for n in names if n.startswith(prefixes))
    return offenders
