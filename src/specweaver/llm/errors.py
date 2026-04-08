# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""LLM-specific exceptions.

Hierarchy:
- LLMError (base)
  - AuthenticationError (invalid/missing API key)
  - RateLimitError (provider rate limit exceeded)
  - ModelNotFoundError (requested model doesn't exist)
  - GenerationError (LLM returned an error during generation)
  - ContentFilterError (response blocked by safety filters)
"""

from __future__ import annotations


class LLMError(Exception):
    """Base exception for all LLM-related errors."""

    def __init__(self, message: str, *, provider: str = "") -> None:
        self.provider = provider
        super().__init__(message)


class AuthenticationError(LLMError):
    """Invalid or missing API credentials."""


class RateLimitError(LLMError):
    """Provider rate limit exceeded. Retry after backoff."""

    def __init__(
        self, message: str, *, provider: str = "", retry_after: float | None = None
    ) -> None:
        self.retry_after = retry_after
        super().__init__(message, provider=provider)


class ModelNotFoundError(LLMError):
    """Requested model does not exist or is not available."""


class GenerationError(LLMError):
    """LLM returned an error during generation."""


class ContentFilterError(LLMError):
    """Response was blocked by the provider's safety/content filters."""
