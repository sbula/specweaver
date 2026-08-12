# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Shared fixtures for the v1 API unit tests.

`tests/CLAUDE.md`: *"unit/ — Fast, isolated. Mock all I/O."* The `/review` and `/implement` routes
build a real LLM adapter through `create_llm_adapter` before they reach any handler the tests
already mock, and that call fails when no provider key is present in the environment. Three tests
therefore passed only on a machine with `GEMINI_API_KEY` exported and returned 500 everywhere else
— not a broken endpoint, a test depending on ambient configuration.

The fixture below supplies the adapter instead. Deliberately **not** an autouse fixture and
deliberately **not** a dummy key in the environment: either would make the suite green while leaving
it dependent on state no assertion mentions, and would hide the next test that starts reaching
outward.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def stub_llm_adapter():
    """Patch `create_llm_adapter` so a route reaches its own logic without a provider key.

    Patched at the definition site rather than in either route's namespace: both import the symbol
    inside the request handler, so a module-level patch on the caller would never be seen.

    Yields the stub adapter so a test can assert against it.
    """
    from specweaver.infrastructure.llm.models import GenerationConfig

    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value="stubbed")
    adapter.available.return_value = True

    with patch(
        "specweaver.infrastructure.llm.factory.create_llm_adapter",
        return_value=(MagicMock(), adapter, GenerationConfig(model="stub-model")),
    ):
        yield adapter
