"""Module with unused imports — auto-fixable by ruff.

DO NOT FIX — this is a test fixture for integration tests.
"""

import json  # noqa: F401 — deliberately unused for testing
import os  # noqa: F401 — deliberately unused for testing
import sys  # noqa: F401 — deliberately unused for testing


def hello() -> str:
    """Return a hello string."""
    return "hello"
