# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Module with unused imports — auto-fixable by ruff.

DO NOT FIX — this is a test fixture for integration tests.
"""

import json  # noqa: F401 — deliberately unused for testing
import os  # noqa: F401 — deliberately unused for testing
import sys  # noqa: F401 — deliberately unused for testing


def hello() -> str:
    """Return a hello string."""
    return "hello"
