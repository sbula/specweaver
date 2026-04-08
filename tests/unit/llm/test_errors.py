# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for specweaver.llm.errors — exception hierarchy."""

from __future__ import annotations

import pytest

from specweaver.llm.errors import (
    AuthenticationError,
    ContentFilterError,
    GenerationError,
    LLMError,
    ModelNotFoundError,
    RateLimitError,
)


class TestLLMError:
    """Base LLMError construction and behaviour."""

    def test_message_preserved(self) -> None:
        exc = LLMError("something broke")
        assert str(exc) == "something broke"

    def test_provider_default_empty(self) -> None:
        exc = LLMError("msg")
        assert exc.provider == ""

    def test_provider_kwarg(self) -> None:
        exc = LLMError("msg", provider="gemini")
        assert exc.provider == "gemini"

    def test_is_exception(self) -> None:
        assert issubclass(LLMError, Exception)


class TestAuthenticationError:
    def test_inherits_llm_error(self) -> None:
        assert issubclass(AuthenticationError, LLMError)

    def test_message_and_provider(self) -> None:
        exc = AuthenticationError("bad key", provider="openai")
        assert str(exc) == "bad key"
        assert exc.provider == "openai"


class TestRateLimitError:
    def test_inherits_llm_error(self) -> None:
        assert issubclass(RateLimitError, LLMError)

    def test_retry_after_default_none(self) -> None:
        exc = RateLimitError("slow down")
        assert exc.retry_after is None

    def test_retry_after_kwarg(self) -> None:
        exc = RateLimitError("slow down", retry_after=30.0)
        assert exc.retry_after == 30.0

    def test_provider_kwarg(self) -> None:
        exc = RateLimitError("slow", provider="claude", retry_after=5)
        assert exc.provider == "claude"
        assert exc.retry_after == 5


class TestModelNotFoundError:
    def test_inherits_llm_error(self) -> None:
        assert issubclass(ModelNotFoundError, LLMError)

    def test_str_matches_message(self) -> None:
        exc = ModelNotFoundError("model xyz not available")
        assert "xyz" in str(exc)


class TestGenerationError:
    def test_inherits_llm_error(self) -> None:
        assert issubclass(GenerationError, LLMError)

    def test_str_conversion(self) -> None:
        """Regression: str(exc) must not raise — caught a real bug."""
        exc = GenerationError("generation failed", provider="gemini")
        assert str(exc) == "generation failed"

    def test_caught_by_llm_error_handler(self) -> None:
        with pytest.raises(LLMError):
            raise GenerationError("boom")


class TestContentFilterError:
    def test_inherits_llm_error(self) -> None:
        assert issubclass(ContentFilterError, LLMError)

    def test_message(self) -> None:
        exc = ContentFilterError("blocked by safety filter")
        assert "safety" in str(exc)
