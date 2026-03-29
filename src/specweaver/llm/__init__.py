# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM adapter layer.

Provides a common async interface for LLM providers.
MVP: Gemini only. Future: OpenAI, Anthropic, Mistral, Ollama, vLLM, Qwen.
"""

from specweaver.llm.router import ModelRouter

__all__ = ["ModelRouter"]
