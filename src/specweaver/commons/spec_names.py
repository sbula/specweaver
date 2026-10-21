# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The module a spec describes is named after it, one way, everywhere."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def module_stem(spec_path: Path) -> str:
    """`greeter_spec.md` → `greeter`: the file's stem without a trailing `_spec`, nothing else."""
    return spec_path.stem.removesuffix("_spec")
