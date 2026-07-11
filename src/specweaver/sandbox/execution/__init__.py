# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unified subprocess execution with cross-platform security boundaries.

Public API:
    SubprocessExecutor — main executor class
    SubprocessResult — frozen result dataclass
    ResourceLimits — frozen resource constraints dataclass
"""

from specweaver.sandbox.execution.executor import SubprocessExecutor
from specweaver.sandbox.execution.models import ResourceLimits, SubprocessResult

__all__ = [
    "ResourceLimits",
    "SubprocessExecutor",
    "SubprocessResult",
]
