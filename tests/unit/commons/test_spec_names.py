# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A spec has one module name, everywhere.

Proves: D-INTL-08 FR-1
Proves: D-INTL-08 NFR-4

| Bucket | Case |
|---|---|
| Happy | `greeter_spec.md` → `greeter` |
| Boundary | `_spec` inside the name stays: `my_spec_tool_spec.md` → `my_spec_tool`; a name without the suffix is itself |
| Degradation | not applicable — a pure name rule |
| Hostile | a second copy of the rule anywhere in `src/` fails this file |
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specweaver.commons.spec_names import module_stem

_SRC = Path(__file__).resolve().parents[3] / "src" / "specweaver"


@pytest.mark.parametrize(
    ("spec", "stem"),
    [
        ("specs/greeter_spec.md", "greeter"),
        ("my_spec_tool_spec.md", "my_spec_tool"),
        ("notes.md", "notes"),
        ("spec.md", "spec"),
        ("_spec.md", ""),
    ],
)
def test_the_stem_drops_only_a_trailing_spec(spec: str, stem: str) -> None:
    assert module_stem(Path(spec)) == stem


def test_no_second_copy_of_the_rule_exists() -> None:
    """NFR-4. Two rules gave one spec two module names (TECH-073)."""
    copies = [
        f"{path.relative_to(_SRC)}:{number}"
        for path in _SRC.rglob("*.py")
        if path.name != "spec_names.py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if re.search(r"""(replace|removesuffix)\(\s*["']_spec["']""", line)
    ]

    assert _SRC.is_dir()
    assert copies == []
