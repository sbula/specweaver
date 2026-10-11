# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Build the adapter for one server entry of the machine settings file.

The entry decides everything about where a call goes: the adapter (its `kind`), the address, the
variable the key is read from, and how many calls may run at once. Nothing else is consulted — no
SDK environment variable, and no other provider's key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
from specweaver.infrastructure.llm.adapters.registry import get_adapter_class

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.core.config.llm_settings import ServerEntry


def adapter_for_server(
    name: str, server: ServerEntry, keys: Mapping[str, str]
) -> AsyncRateLimiterAdapter:
    """The adapter for server `name`, limited to its `max_parallel` calls at once."""
    adapter_cls = get_adapter_class(server.kind)
    api_key = keys.get(server.api_key_env, "") if server.api_key_env else None
    adapter = adapter_cls(api_key=api_key, base_url=server.base_url)
    address = server.base_url or getattr(adapter_cls, "default_base_url", None) or name
    return AsyncRateLimiterAdapter(adapter, limit=server.max_parallel, key=name, address=address)
