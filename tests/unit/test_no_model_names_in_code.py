# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""No model name is written into the code: the `default` role is the one fallback, in one place.

Proves: C-FLOW-13 FR-11

Measured 2026-09-27: eleven copies of `"gemini-3-flash-preview"` decided which model a step called
when nothing else did. A string literal that is exactly a model id is the shape they all had.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src" / "specweaver"
_MODEL_ID = re.compile(r"^(gemini|gpt|claude|mistral|qwen|o\d)[-.][\w.-]+$")


def _model_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        f"{path.relative_to(_SRC)}:{node.lineno} {node.value}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _MODEL_ID.match(node.value)
    ]


def test_no_source_file_names_a_model() -> None:
    found = [hit for path in sorted(_SRC.rglob("*.py")) for hit in _model_literals(path)]

    assert found == [], "a model is chosen in the settings file, never in code:\n" + "\n".join(
        found
    )
