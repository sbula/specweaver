# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every log line reaches the project's handlers: loggers are named for their module.

`D-FLOW-04` FR-9. `setup_logging` configures the `specweaver` logger, so a logger reaches the
project's console and file only when it sits below it: `getLogger(__name__)`, or an f-string that
starts with `{__name__}`. Refused, as `path:line`:

* `getLogger` with any other name, or with none (the root logger);
* a call on the root logger itself — `logging.error(...)`, `logging.critical(...)` and the rest.

`telemetry_logger.py`, which configures `specweaver`, may name it. `print()` is ruff's `T20`.

Usage: `python scripts/check_logger_names.py [paths...]` (default `src`). Exit 1 on any offender.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_ROOT_CALLS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
)
_SET_UP = "telemetry_logger.py"


def _under_module(arg: ast.expr) -> bool:
    if isinstance(arg, ast.Name):
        return arg.id == "__name__"
    if isinstance(arg, ast.JoinedStr) and arg.values:
        first = arg.values[0]
        return isinstance(first, ast.FormattedValue) and ast.unparse(first.value) == "__name__"
    return False


def _is_logging(node: ast.expr) -> bool:
    return isinstance(node, ast.Name) and node.id == "logging"


def stray_loggers(source: str, path: str = "") -> list[int]:
    """The lines in `source` whose log lines would bypass the project's handlers."""
    set_up = path.endswith(_SET_UP)
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if not _is_logging(node.func.value):
            continue
        name = node.func.attr
        if name == "getLogger":
            arg = node.args[0] if node.args else None
            allowed = arg is not None and (
                _under_module(arg)
                or (set_up and isinstance(arg, ast.Constant) and arg.value == "specweaver")
            )
            if not allowed:
                found.append(node.lineno)
        elif name in _ROOT_CALLS:
            found.append(node.lineno)
    return sorted(found)


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in (argv or ["src"])]
    offenders: list[str] = []
    for root in roots:
        for path in sorted(root.rglob("*.py") if root.is_dir() else [root]):
            try:
                found = stray_loggers(path.read_text(encoding="utf-8"), str(path))
            except SyntaxError as exc:
                offenders.append(f"{path}:{exc.lineno}: does not parse")
                continue
            offenders.extend(f"{path}:{line}" for line in found)
    for offender in offenders:
        print(offender)
    print(f"Loggers outside their module: {len(offenders)}")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
