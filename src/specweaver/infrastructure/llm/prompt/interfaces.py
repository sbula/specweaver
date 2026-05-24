# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from typing import Protocol, runtime_checkable


@runtime_checkable
class PromptContentSource(Protocol):
    """Duck-typed structural protocol for pluggable context sources."""

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        """Return the fully formatted string content (including XML tags and escaping).

        If char_limit is provided, the raw payload should be truncated before formatting and escaping.
        """
        ...

    def get_prompt_label(self) -> str:
        """Return the label/name of the context block."""
        ...
