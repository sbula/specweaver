# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Why a Python-only code rule skips a file, or None when the file is Python."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from specweaver.commons.languages import language_of

if TYPE_CHECKING:
    from pathlib import Path


def python_only(rule_id: str, spec_path: Path | None) -> str | None:
    """The SKIP reason for a file that is not Python, naming its language; None for Python.

    Without a path, or with an ending no language claims, the language is unknown and the text is
    never parsed as Python.
    """
    language = language_of(spec_path) if spec_path is not None else None
    if language == "python":
        return None
    return f"{language or 'language unknown'}: {rule_id} checks Python only"


def parse_python(text: str) -> ast.Module:
    """The parsed Python text; raises `SyntaxError`. A byte order mark at the very start is dropped,
    as Python drops it from a file on disk; one anywhere else stays an error."""
    return ast.parse(text.removeprefix("\ufeff"))


def python_tree(rule_id: str, spec_text: str, spec_path: Path | None) -> ast.Module | str:
    """The parsed Python file, or why a rule that walks it skips: another language, or a syntax
    error (C01 reports that one itself)."""
    reason = python_only(rule_id, spec_path)
    if reason is not None:
        return reason
    try:
        return parse_python(spec_text)
    except SyntaxError:  # expected: the rule reports itself skipped
        return "Cannot parse file (syntax error)"
