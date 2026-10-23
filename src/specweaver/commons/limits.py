# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Limits that more than one module must agree on."""

from __future__ import annotations

#: The largest `CONSTITUTION.md` loaded without a warning, in bytes, unless a project sets its own.
DEFAULT_MAX_CONSTITUTION_SIZE = 5120
