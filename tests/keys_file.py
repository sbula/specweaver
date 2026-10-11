# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Write a `keys.env` for a test's data directory: the one place SpecWeaver reads API keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def write_keys(data_dir: Path, **keys: str) -> Path:
    """`keys.env` in `data_dir`, readable by its owner only, as SpecWeaver demands."""
    path = data_dir / "keys.env"
    path.write_text("".join(f"{name}={value}\n" for name, value in keys.items()), encoding="utf-8")
    path.chmod(0o600)
    return path
