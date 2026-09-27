# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
from typing import ClassVar

from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter

logger = logging.getLogger(__name__)


class QwenAdapter(OpenAIAdapter):
    """Adapter for Alibaba Qwen models using OpenAI compatible API."""

    provider_name = "qwen"
    api_key_env_var = "DASHSCOPE_API_KEY"

    # No default address: DashScope's current addresses carry the account's workspace, and the
    # one address without it is the legacy domain.
    default_base_url: ClassVar[str | None] = None
    #: DashScope documents only `max_tokens`.
    output_limit_field: ClassVar[str] = "max_tokens"
    sends_sampling: ClassVar[bool] = True
