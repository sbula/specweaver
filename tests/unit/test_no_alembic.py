# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Alembic is gone: a migration setup nothing runs reads as migrations that work.

Proves: TECH-090 FR-10
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def test_no_alembic_files_remain() -> None:
    assert not (_ROOT / "alembic.ini").exists()
    assert not (_ROOT / "alembic").exists()
    assert not (_ROOT / "tests" / "unit" / "alembic").exists()


def test_alembic_is_not_a_dependency() -> None:
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert not re.search(r'"alembic[<>=~!\s"]', text)


def test_no_module_imports_alembic() -> None:
    importing = [
        str(path.relative_to(_ROOT))
        for root in ("src", "tests")
        for path in (_ROOT / root).rglob("*.py")
        if re.search(r"^\s*(import alembic|from alembic)", path.read_text(encoding="utf-8"), re.M)
    ]

    assert importing == []
