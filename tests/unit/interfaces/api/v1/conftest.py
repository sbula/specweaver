# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Shared fixtures for the v1 API unit tests.

`tests/CLAUDE.md`: *"unit/ — Fast, isolated. Mock all I/O."* The `/review` and `/implement` routes
build a real LLM adapter through `RoleResolver` before they reach any handler the tests already
mock, and that call fails when no role is set in the settings files. Three tests
therefore once passed only on a machine with a provider key exported and returned 500 everywhere
else — not a broken endpoint, a test depending on ambient configuration.

The fixture below supplies the adapter instead. Deliberately **not** an autouse fixture and
deliberately **not** a role in the settings files: either would make the suite green while leaving
it dependent on state no assertion mentions, and would hide the next test that starts reaching
outward.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.scripted_llm import doubled_llm


@pytest.fixture()
def stub_llm_adapter():
    """Double the resolver so a route reaches its own logic without a configured model.

    Yields the stub adapter so a test can assert against it.
    """
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value="stubbed")
    adapter.flush_async = AsyncMock()
    adapter.available.return_value = True

    with doubled_llm(adapter, model="stub-model"):
        yield adapter
