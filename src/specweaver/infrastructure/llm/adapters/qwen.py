# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import os
from typing import Any, ClassVar

from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
from specweaver.infrastructure.llm.telemetry import CostEntry


class QwenAdapter(OpenAIAdapter):
    """Adapter for Alibaba Qwen models using OpenAI compatible API."""

    provider_name = "qwen"
    api_key_env_var = "QWEN_API_KEY"
    default_costs: ClassVar[dict[str, CostEntry]] = {
        "qwen3-max": CostEntry(0.00200, 0.00600),
        "qwen3.5-plus": CostEntry(0.00080, 0.00240),
        "qwen-max-latest": CostEntry(0.00200, 0.00600),
        "qwen-plus-latest": CostEntry(0.00040, 0.00120),
    }

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize the Qwen adapter."""
        super().__init__(api_key=api_key or os.environ.get(self.api_key_env_var, ""))

    def _get_client(self) -> Any:
        if self._client is None:
            import openai  # type: ignore[import-not-found]

            self._client = openai.AsyncOpenAI(
                api_key=self._api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        return self._client
