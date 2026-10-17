# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No caught error is lost: every `except` logs, raises, uses its error, or states its reason.

`D-FLOW-04` FR-6. A handler passes when its body

* calls a logger — a method on a name that is `log`, `logger` or ends in `logger`;
* raises;
* names the error it caught (`except E as exc:` and `exc` appears in the body); or
* its `except` line carries `# expected: <why>`, with a reason after the colon.

Anything else drops the error without a trace and is named as `path:line`. A file that does not parse
fails too: an unread file is not a clean one. The count of stated reasons is printed, so their growth
stays visible.

Usage: `python scripts/check_lost_errors.py [paths...]` (default `src`). Exit 1 on any offender.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_LOG_METHODS = frozenset(
    {"debug", "info", "warning", "warn", "error", "exception", "critical", "log"}
)
_REASON = re.compile(r"#\s*expected:\s*\S")


def _is_logger(node: ast.expr) -> bool:
    name = node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", "")
    name = name.lower().lstrip("_")
    return name in {"log", "logger"} or name.endswith("logger")


def _handled(handler: ast.ExceptHandler) -> bool:
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            return True
        if isinstance(node, ast.Name) and handler.name and node.id == handler.name:
            return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _LOG_METHODS
            and _is_logger(node.func.value)
        ):
            return True
    return False


def lost_errors(source: str) -> list[int]:
    """The lines of every `except` in `source` that drops its error without a stated reason."""
    lines = source.splitlines()
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ExceptHandler)
        and not _handled(node)
        and not _REASON.search(lines[node.lineno - 1])
    )


def reasons(source: str) -> int:
    return sum(1 for line in source.splitlines() if _REASON.search(line))


def main(argv: list[str]) -> int:
    roots = [Path(p) for p in (argv or ["src"])]
    offenders: list[str] = []
    stated = 0
    for root in roots:
        for path in sorted(root.rglob("*.py") if root.is_dir() else [root]):
            source = path.read_text(encoding="utf-8")
            try:
                found = lost_errors(source)
            except SyntaxError as exc:
                offenders.append(f"{path}:{exc.lineno}: does not parse")
                continue
            stated += reasons(source)
            offenders.extend(f"{path}:{line}" for line in found)
    for offender in offenders:
        print(offender)
    print(f"Lost errors: {len(offenders)}; {stated} reason(s) stated with '# expected:'")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
