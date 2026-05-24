# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Backward-compatibility facade for RenderProfile and PromptSlot."""

from specweaver.infrastructure.llm.prompt.profiles import (
    _DEFAULT_PROFILE,
    PromptSlot,
    RenderProfile,
)

__all__ = ["_DEFAULT_PROFILE", "PromptSlot", "RenderProfile"]
