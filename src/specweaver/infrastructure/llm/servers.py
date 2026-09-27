# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Build the adapter for one server entry of the machine settings file.

The entry decides everything about where a call goes: the adapter (its `kind`), the address, the
variable the key is read from, and how many calls may run at once. Nothing else is consulted — no
SDK environment variable, and no other provider's key.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
from specweaver.infrastructure.llm.adapters.registry import get_adapter_class

if TYPE_CHECKING:
    from specweaver.core.config.llm_settings import ServerEntry


def adapter_for_server(name: str, server: ServerEntry) -> AsyncRateLimiterAdapter:
    """The adapter for server `name`, limited to its `max_parallel` calls at once."""
    adapter_cls = get_adapter_class(server.kind)
    # No key variable means the server needs no key (`None`); a named but unset one is a missing
    # key (`""`), which leaves the adapter unavailable rather than reading any other variable.
    api_key = None if server.api_key_env is None else os.environ.get(server.api_key_env, "")
    adapter = adapter_cls(api_key=api_key, base_url=server.base_url)
    return AsyncRateLimiterAdapter(adapter, limit=server.max_parallel, key=name)
