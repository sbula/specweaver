# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Structured logging from the LLM adapters. `TECH-051` CB-1 moved one test OUT of this file.

`test_malformed_protocol_payload_emits_error_log` lived here and had nothing to do with LLM
logging: it drove `GRPCParser` and was, measurably, the only protector of that parser's error path
in the whole suite. It now lives in
`tests/unit/sandbox/protocol/core/protocol/test_grpc_parser.py`, the file named after the code it
covers — which had been empty since it was created.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
from specweaver.infrastructure.llm.errors import AuthenticationError
from specweaver.infrastructure.llm.models import GenerationConfig


@pytest.mark.asyncio
async def test_llm_adapter_exception_emits_structured_error_log(caplog):
    """Story 2: [Boundary/Edge Case] LLM Adapter HTTP exceptions emit structured JSON logs."""
    # We use caplog to intercept the logging module at the adapter layer
    adapter = OpenAIAdapter(api_key="fake")
    config = GenerationConfig(model="gpt-4o")

    # Force the adapter to throw an authentication error by mocking the internal client
    with patch("openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        # Create an error that looks like openai.AuthenticationError
        import openai

        mock_client.chat.completions.create.side_effect = openai.AuthenticationError(
            message="Invalid API Key",
            response=MagicMock(request=MagicMock()),
            body=None,
        )
        mock_client_cls.return_value = mock_client

        with caplog.at_level(logging.ERROR), pytest.raises(AuthenticationError):
            await adapter.generate([], config)

    # Assert the adapter logged the error securely
    error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(error_logs) >= 1
    # Check that the logger is indeed from the openai adapter
    assert error_logs[0].name == "specweaver.infrastructure.llm.adapters.openai"
    assert "authentication failed" in error_logs[0].message.lower()


@pytest.mark.asyncio
async def test_fallback_adapter_writes_warning_logs(caplog):
    """Story 3: [Graceful Degradation] Fallback adapter paths successfully write warning logs."""
    from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
    from specweaver.infrastructure.llm.models import GenerationConfig

    adapter = OpenAIAdapter(api_key="fake")
    config = GenerationConfig(model="gpt-4o")

    with patch("openai.AsyncOpenAI") as mock_client_cls:
        mock_client = AsyncMock()
        import openai

        mock_client.chat.completions.create.side_effect = openai.RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(request=MagicMock()),
            body=None,
        )
        mock_client_cls.return_value = mock_client

        with caplog.at_level(logging.WARNING):
            import contextlib

            with contextlib.suppress(Exception):
                await adapter.generate([], config)

    warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning_logs) >= 1
    assert warning_logs[0].name == "specweaver.infrastructure.llm.adapters.openai"
    assert "rate limit" in warning_logs[0].message.lower()
