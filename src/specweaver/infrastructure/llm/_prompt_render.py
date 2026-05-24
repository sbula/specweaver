# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Backward-compatibility facade for prompt rendering functions."""

import logging

from specweaver.infrastructure.llm.prompt.render import (
    _render_contexts,
    _render_mentioned,
    _render_topology,
    render_blocks,
    render_files,
)

logger = logging.getLogger(__name__)

__all__ = [
    "_render_contexts",
    "_render_mentioned",
    "_render_topology",
    "render_blocks",
    "render_files",
]
