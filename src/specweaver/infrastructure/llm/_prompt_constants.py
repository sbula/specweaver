# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Backward-compatibility facade for prompt constants."""

from specweaver.infrastructure.llm.prompt.constants import (
    _CONSTITUTION_PREAMBLE,
    detect_language,
)

__all__ = ["_CONSTITUTION_PREAMBLE", "detect_language"]
