# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An allow-list entry is a path or a glob; `*` stays inside one folder, `**` spans folders.

Proves: C-EXEC-06 FR-5

| Bucket | Case |
|---|---|
| Happy | an exact path and a `*` glob match their file |
| Boundary | `**` matches zero or more folders |
| Degradation | an empty allow-list matches nothing |
| Hostile | `*` never crosses a folder; `..` in a path never matches a glob above it |
"""

from __future__ import annotations

import pytest

from specweaver.sandbox.git.core.worktree_ops import path_allowed


@pytest.mark.parametrize(
    ("path", "patterns"),
    [
        ("src/foo.py", ["src/foo.py"]),
        ("src/foo.py", ["src/*.py"]),
        ("src/foo.py", ["src/**/*.py"]),
        ("src/a/b/foo.py", ["src/**/*.py"]),
        ("tests/test_x.py", ["src/*.py", "tests/test_*.py"]),
    ],
)
def test_matches(path: str, patterns: list[str]) -> None:
    assert path_allowed(path, patterns)


@pytest.mark.parametrize(
    ("path", "patterns"),
    [
        ("src/a/foo.py", ["src/*.py"]),
        ("secret.py", ["src/**/*.py"]),
        ("src/foo.py", []),
        ("src/../secret.py", ["src/*.py"]),
        ("src/foo.pyc", ["src/foo.py"]),
    ],
)
def test_does_not_match(path: str, patterns: list[str]) -> None:
    assert not path_allowed(path, patterns)
