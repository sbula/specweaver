# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The line a key path sits on in YAML loaded by ruamel's round-trip loader."""

from __future__ import annotations

from typing import Any


def yaml_line(data: Any, path: tuple[str, ...]) -> int:
    """The 1-based line of the deepest key of `path` found in `data`, else 1."""
    line, node = 1, data
    for part in path:
        marks = getattr(node, "lc", None)
        if marks is None or not isinstance(node, dict) or part not in node:
            break
        line = marks.key(part)[0] + 1
        node = node[part]
    return line
