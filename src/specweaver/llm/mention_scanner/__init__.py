# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Mention scanner — extract file/spec references from LLM responses.

Re-exports the public API for convenient imports::

    from specweaver.llm.mention_scanner import extract_mentions, ResolvedMention
"""

from specweaver.llm.mention_scanner.models import ResolvedMention
from specweaver.llm.mention_scanner.scanner import extract_mentions

__all__ = ["ResolvedMention", "extract_mentions"]
