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

`LLMAdapterError` stands outside that hierarchy deliberately: the others are provider failures
during a call, this one is a failure to *build* an adapter at all. It lives here rather than in
`factory` because `_rate_limit` raises it and `factory` imports `_rate_limit`.
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


class LLMAdapterError(Exception):
    """Raised when an LLM adapter cannot be created or validated.

    Defined here, below `factory`, and not in it. `factory` needs `_rate_limit`'s adapter and
    `_rate_limit` needs this exception, so holding it in `factory` forces each to defer its import
    inside a function — the workaround `check_coupling` names when it says *"break it by moving the
    shared contract down, not by deferring an import inside a function"*. Deferring hides a cycle
    from the interpreter without removing it, leaving the modules inextricable.

    Not a subclass of `LLMError`: eleven files catch these separately and widening the hierarchy
    would silently change what their `except LLMError` blocks catch.
    """
