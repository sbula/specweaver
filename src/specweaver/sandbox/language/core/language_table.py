# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One lookup for the per-language factories: a table row, imported on use, or a refusal."""

from __future__ import annotations

import importlib
from typing import Any


def language_class(table: dict[str, str], language: str, what: str) -> Any:
    """The class `table` names for `language` (`module:class` under `sandbox.language.core`).

    Raises `ValueError` naming the language when the table has no row for it: no part of a run
    falls back to Python.
    """
    row = table.get(language)
    if row is None:
        msg = f"no {what} for language {language!r}"
        raise ValueError(msg)
    module, name = row.split(":")
    return getattr(importlib.import_module(f"specweaver.sandbox.language.core.{module}"), name)
