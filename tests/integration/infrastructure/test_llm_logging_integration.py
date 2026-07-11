# mypy: ignore-errors
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
from specweaver.infrastructure.llm.errors import AuthenticationError
from specweaver.infrastructure.llm.models import GenerationConfig
from specweaver.sandbox.protocol.core.grpc_parser import GRPCParser


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


def test_malformed_protocol_payload_emits_error_log(caplog):
    """Story 4: [Hostile/Wrong Input] Malformed payload parsing in protocol sandbox emits an error log."""
    from specweaver.sandbox.protocol.core.protocol_interfaces import ProtocolSchemaError

    parser = GRPCParser()

    with caplog.at_level(logging.DEBUG), pytest.raises(ProtocolSchemaError):
        # A completely invalid syntax string
        parser.extract_endpoints("syntax = proto3; \n message invalid { int missing_semicolon }")

    # The parser internally emits a debug/error before raising
    logs = [r for r in caplog.records if r.name == "specweaver.sandbox.protocol.core.grpc_parser"]
    assert len(logs) >= 1
    # Check the error log was captured
    assert "Failed to parse gRPC schema" in logs[-1].message or "parse" in logs[-1].message.lower()
