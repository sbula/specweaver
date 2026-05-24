# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Backward-compatibility facade for PromptBuilder."""

import logging

from specweaver.infrastructure.llm.prompt.block import _ContentBlock
from specweaver.infrastructure.llm.prompt.builder import PromptBuilder
from specweaver.infrastructure.llm.prompt.constants import detect_language

logger = logging.getLogger(__name__)

__all__ = ["PromptBuilder", "_ContentBlock", "detect_language"]
