# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`available()` means the same thing for every adapter, so it is defined once.

`TECH-037`. Four concrete adapters each wrote `return bool(self._api_key)`. It was declared
abstract on `LLMAdapter`, which obliged every adapter to restate an answer none of them varied.
"""

from __future__ import annotations

import pytest

from specweaver.infrastructure.llm.adapters.anthropic import AnthropicAdapter
from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
from specweaver.infrastructure.llm.adapters.mistral import MistralAdapter
from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
from specweaver.infrastructure.llm.adapters.qwen import QwenAdapter

ADAPTERS = [AnthropicAdapter, GeminiAdapter, MistralAdapter, OpenAIAdapter, QwenAdapter]


@pytest.mark.parametrize("adapter_cls", ADAPTERS, ids=lambda c: c.__name__)
class TestAvailable:
    def test_a_configured_adapter_is_available(self, adapter_cls: type) -> None:
        assert adapter_cls(api_key="sk-test").available() is True

    def test_an_unconfigured_adapter_is_not(self, adapter_cls: type) -> None:
        """An empty key is not a key. The factory uses this to decide whether to offer the model."""
        assert adapter_cls(api_key="").available() is False

    def test_it_is_not_redeclared_on_the_adapter(self, adapter_cls: type) -> None:
        """Four identical copies became one default; a regression would restore a per-adapter one."""
        assert "available" not in vars(adapter_cls)
