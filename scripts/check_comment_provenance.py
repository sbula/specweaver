#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Code is a document of the present. No registry ID in a `src/` comment or docstring.

A comment naming the ticket that paid for a line adds nothing to the reader, who needs to know what
the line does now. Git holds the provenance, and the design documents hold the reasoning.

**The reference also rots on its own.** `ADR-004` changed what every `INT-US` entry means, which
left 104 references in `src/` naming a scope their authors never intended -- and nothing read them,
so nothing caught it. `TECH-059` removed 256 such references across ~130 files.

**Zero-tolerance, not ratcheted.** The sweep reached zero, so there is no legacy set to carry
forward, and a ratchet at zero is just a slower way of saying the same thing.

**Why this is not a rule inside `check_conventions.py`,** where its siblings R1-R8 live: that file
sits at exactly 600 lines, its RED ceiling. R6, R7 and R8 were each moved to a sibling for the same
headroom reason, and `TECH-020` records buying headroom by condensing comments as the pattern to
stop repeating -- so a ninth rule gets its own gate rather than a shave off the prose that explains
the other eight.

Three things are deliberately out of scope:

* **Live code.** A string literal is behaviour. `engine/session.py` carries `C-EXEC-06` in four
  user-facing error messages and `mcp/interfaces/tool.py` holds `"protocolVersion": "2024-11-05"`;
  rewriting either is a code change with its own risk, not a comment cleanup.
* **`tests/` and `scripts/`.** A `Proves:` tag is read by `check_fr_coverage.py`, so flagging it
  would set two gates against each other -- the trap R5 in `check_conventions.py` names. And a gate
  script's docstring usually records the measurement that justifies its rule, which is arguably
  present-tense justification rather than history. That is a separate decision.
* **Validation rule IDs.** `C01`..`C13`, `S07`, `S12` are domain vocabulary that outlives every
  ticket touching them. The ID pattern below is anchored so they cannot match; a looser
  `[A-Z]-?\\d{2}` flags them and the reflex fix is a fresh allowlist.

Usage:
    python scripts/check_comment_provenance.py [path ...]   # defaults to src/

Exit 0 when clean, 1 on any finding or any file that cannot be parsed.
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = REPO_ROOT / "src"

#: A registry ID, anchored on what each family actually has: the `INT-US-` prefix, the `TECH-` prefix
#: with exactly three digits, or a DAL letter joined to an UPPERCASE topic word and a number. None of
#: those shapes can be reached by `C09` or `S07`, which is the point -- see the module docstring.
_REGISTRY_ID = re.compile(r"\b(?:INT-US-\d+(?:-(?:SF\d+|SUB))?|TECH-\d{3}|[A-E]-[A-Z]{2,}-\d+)\b")


def _prose_lines(source: str) -> set[int]:
    """Line numbers occupied by a comment or a docstring.

    Docstrings are found through the AST rather than by matching quotes, so an ordinary string
    literal -- which is behaviour -- is never mistaken for prose.
    """
    lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            lines.add(token.start[0])
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


def offending_prose(path: Path) -> list[str]:
    """Every comment or docstring line in `path` naming a registry ID, one message each.

    Raises:
        SyntaxError: the file cannot be parsed by `ast`.
        tokenize.TokenError: the file cannot be tokenized -- a distinct exception, and NOT a
            `SyntaxError` subclass, so catching only the latter lets an unparseable file through as
            clean. A checker that cannot read its subject must say so rather than pass by accident.
    """
    source = path.read_text(encoding="utf-8")
    prose = _prose_lines(source)
    rel = path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else str(path)

    found: list[str] = []
    for number, line in enumerate(source.splitlines(), 1):
        if number not in prose:
            continue
        ids = _REGISTRY_ID.findall(line)
        if ids:
            found.append(
                f"{rel}:{number}: names {', '.join(sorted(set(ids)))} — {line.strip()[:60]}"
            )
    return found


def _python_files(targets: list[Path]) -> list[Path]:
    out: list[Path] = []
    for target in targets:
        if target.is_dir():
            out.extend(sorted(target.rglob("*.py")))
        elif target.suffix == ".py":
            out.append(target)
    return out


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    targets = [Path(a) for a in args] or [DEFAULT_ROOT]

    findings: list[str] = []
    unreadable: list[str] = []
    for path in _python_files(targets):
        try:
            findings.extend(offending_prose(path))
        except (SyntaxError, tokenize.TokenError, UnicodeDecodeError) as exc:
            unreadable.append(f"{path}: cannot parse — {exc}")

    print("Comment provenance check")
    for message in unreadable:
        print(f"  UNREADABLE: {message}")
    for message in findings:
        print(f"  {message}")

    if not findings and not unreadable:
        print("  no registry IDs in comments or docstrings")
        return 0

    if findings:
        print(
            f"\nFAIL  {len(findings)} comment(s) carry a registry ID.\n"
            "Code documents the present: state what is true now and drop the ticket reference. Where\n"
            "the comment is only an account of a past change, delete it — git holds that history."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
