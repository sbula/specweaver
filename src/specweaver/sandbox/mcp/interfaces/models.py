# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Standard return type for MCP Explorer Tool."""

    status: str  # "success" or "error"
    message: str = ""
    data: Any = None


class MCPToolError(Exception):
    """Raised when an MCP Explorer Tool operation is blocked by role or constraints."""
