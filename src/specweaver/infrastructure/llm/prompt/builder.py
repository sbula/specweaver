# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Structured, token-aware prompt builder with XML-tagged output.

Assembles prompts from instructions, files, and context blocks into a
structured XML format.  Supports hybrid truncation (priority-ordered +
proportional redistribution) when a ``TokenBudget`` is provided.

Usage::

    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

    prompt = (
        PromptBuilder()
        .add_instructions("Review this spec for clarity.")
        .add_file(spec_path, priority=1)
        .add_file(code_path, priority=2)
        .add_context(topology_summary, "topology")
        .build()
    )
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.models import TokenBudget
    from specweaver.infrastructure.llm.prompt.profiles import RenderProfile

from specweaver.infrastructure.llm.escaping import apply_escaping
from specweaver.infrastructure.llm.prompt.adders import PromptBuilderAddersMixin
from specweaver.infrastructure.llm.prompt.block import _ContentBlock

logger = logging.getLogger(__name__)


class PromptBuilder(PromptBuilderAddersMixin):
    """Assemble structured, token-aware prompts with XML-tagged output.

    Args:
        budget: Optional token budget for truncation awareness.
        adapter: Optional LLM adapter for ``estimate_tokens()``.  When
            provided, token counts use the adapter's heuristic.  Otherwise
            the default ``len(text) // 4`` estimate is used.
    """

    def __init__(
        self,
        budget: TokenBudget | None = None,
        adapter: LLMAdapter | None = None,
        *,
        budget_scale_factor: float = 1.0,
        skeleton_files: dict[str, str] | None = None,
        profile: RenderProfile | None = None,
    ) -> None:
        self._budget = budget
        self._adapter = adapter
        self._scale = max(0.1, min(budget_scale_factor, 2.0))  # clamp to [0.1, 2.0]
        self._auto_scale = budget_scale_factor == 1.0  # auto-scale when default
        self._blocks: list[_ContentBlock] = []
        self._skeleton_files: dict[str, str] = skeleton_files or {}

        if profile is None:
            import warnings

            from specweaver.infrastructure.llm._prompt_profiles import _DEFAULT_PROFILE

            warnings.warn(
                "PromptBuilder created without explicit profile — using _DEFAULT_PROFILE. Pass a RenderProfile for explicit slot control.",
                DeprecationWarning,
                stacklevel=2,
            )
            self._profile = _DEFAULT_PROFILE
        else:
            self._profile = profile

    def _is_slot_active(self, slot: Any) -> bool:
        """Check if a slot is active in the current profile."""
        return slot in self._profile.active_slots

    def clone(self) -> PromptBuilder:
        """Create a deep copy of this PromptBuilder."""
        import copy

        # We pass 1.0 for budget_scale_factor and then restore the actual values
        builder = PromptBuilder(
            budget=self._budget,
            adapter=self._adapter,
            budget_scale_factor=1.0,
            skeleton_files=self._skeleton_files.copy() if self._skeleton_files else None,
            profile=self._profile,
        )
        builder._scale = self._scale
        builder._auto_scale = self._auto_scale
        builder._blocks = copy.deepcopy(self._blocks)
        return builder

    def build(self) -> str:
        """Assemble the prompt as an XML-tagged string.

        If a ``TokenBudget`` was provided, applies hybrid truncation:
        1. Instructions (priority 0) are always included in full.
        2. Remaining budget is distributed by priority order.
        3. Within the same priority, surplus from underflow is
           redistributed proportionally.
        4. Truncated blocks get a ``[truncated]`` marker.

        Returns:
            The assembled prompt string.
        """
        if not self._blocks:
            return ""

        blocks = list(self._blocks)
        logger.debug(
            "PromptBuilder.build: %d blocks, budget=%s",
            len(blocks),
            self._budget.limit if self._budget else "unlimited",
        )

        if self._budget is not None:
            if self._auto_scale:
                self._compute_auto_scale(blocks)
            blocks = self._apply_truncation(blocks)

        return self._render(blocks)

    def _compute_auto_scale(self, blocks: list[_ContentBlock]) -> None:
        """Auto-adjust ``_scale`` based on content-to-budget ratio.

        When main content (instructions + files + context) is small
        relative to the budget, topology gets more room.  When content
        is large, topology is compressed.  This mirrors Aider's
        approach of dynamically sizing the repo map.

        Thresholds:
        - Non-topology < 25% of budget → scale up to 1.5
        - Non-topology > 75% of budget → scale down to 0.5
        - Otherwise → keep at 1.0
        """
        assert self._budget is not None

        has_topology = any(b.kind == "topology" for b in blocks)
        if not has_topology:
            return  # No topology to scale, keep default

        non_topology_tokens = sum(b.tokens for b in blocks if b.kind != "topology")
        ratio = non_topology_tokens / max(self._budget.limit, 1)

        if ratio < 0.25:
            self._scale = 1.5  # Lots of room → expand topology
        elif ratio > 0.75:
            self._scale = 0.5  # Tight budget → compress topology
        # else: keep at 1.0

    def _count(self, text: str) -> int:
        """Estimate token count for *text*."""
        if self._adapter is not None:
            return self._adapter.estimate_tokens(text)
        return len(text) // 4

    def _apply_truncation(self, blocks: list[_ContentBlock]) -> list[_ContentBlock]:
        """Apply hybrid priority-ordered + proportional truncation."""
        assert self._budget is not None

        limit = self._budget.limit
        # Apply dynamic scaling
        limit = int(limit * self._scale)
        if limit <= 0:
            return blocks

        # 1. Instructions always included in full
        instruction_tokens = sum(b.tokens for b in blocks if b.priority == 0)
        remaining = limit - instruction_tokens
        if remaining <= 0:
            # Only instructions fit — drop everything else
            return [b for b in blocks if b.priority == 0]

        # 2. Group non-instruction blocks by priority
        content_blocks = [b for b in blocks if b.priority > 0]
        if not content_blocks:
            return blocks

        # Sort by priority (lower = higher priority)
        priority_groups: dict[int, list[_ContentBlock]] = {}
        for block in content_blocks:
            priority_groups.setdefault(block.priority, []).append(block)

        result = [b for b in blocks if b.priority == 0]
        budget_left = remaining

        for prio in sorted(priority_groups):
            group = priority_groups[prio]
            group_tokens = sum(b.tokens for b in group)

            if group_tokens <= budget_left:
                # Entire group fits
                result.extend(group)
                budget_left -= group_tokens
            else:
                # Proportional redistribution within this priority
                result.extend(
                    self._truncate_group(group, budget_left),
                )
                budget_left = 0
                break  # No budget left for lower-priority groups

        # Update budget tracking
        total_used = sum(b.tokens for b in result)
        self._budget.add(total_used)

        return result

    def _truncate_group(
        self,
        group: list[_ContentBlock],
        available: int,
    ) -> list[_ContentBlock]:
        """Proportionally truncate blocks within the same priority group.

        Each block gets a share proportional to its original size.
        Blocks that are smaller than their share keep their full content
        and the surplus is redistributed to the remaining blocks.
        """
        if available <= 0:
            return []

        total = sum(b.tokens for b in group)
        if total == 0:
            return group

        result: list[_ContentBlock] = []

        # Calculate proportional shares
        shares = {i: int((b.tokens / total) * available) for i, b in enumerate(group)}

        for i, block in enumerate(group):
            share = shares[i]
            if block.tokens <= share:
                # Block fits within its share — no truncation
                result.append(block)
            elif share > 0:
                # Truncate to share
                char_limit = share * 4  # reverse of len//4 estimate
                if block.source is not None:
                    try:
                        truncated_text = block.source.get_prompt_content(char_limit=char_limit)
                    except TypeError:
                        # Fallback for adapters without char_limit support
                        truncated_text = block.text[:char_limit] + "\n[truncated]"
                    tokens = self._count(truncated_text)
                    result.append(
                        _ContentBlock(
                            text=truncated_text,
                            priority=block.priority,
                            kind=block.kind,
                            label=block.label,
                            language=block.language,
                            file_path=block.file_path,
                            tokens=tokens,
                            truncated=True,
                            escaping="raw",
                            source=block.source,
                        )
                    )
                else:
                    # Perform character slicing on the raw text before escaping is applied
                    truncated_text = block.text[:char_limit] + "\n[truncated]"
                    # Recalculate escaped token footprint of the truncated block
                    escaped_text = apply_escaping(truncated_text, block.escaping)
                    tokens = self._count(escaped_text)
                    result.append(
                        _ContentBlock(
                            text=truncated_text,
                            priority=block.priority,
                            kind=block.kind,
                            label=block.label,
                            language=block.language,
                            file_path=block.file_path,
                            tokens=tokens,
                            truncated=True,
                            escaping=block.escaping,
                        ),
                    )
            # else: share == 0, block is dropped entirely

        return result

    @staticmethod
    def _render_files(blocks: list[_ContentBlock]) -> str | None:
        """Render ``<file_contents>`` XML from file blocks."""
        from specweaver.infrastructure.llm.prompt.render import render_files

        return render_files(blocks)

    def _render(self, blocks: list[_ContentBlock]) -> str:
        """Render blocks into XML-tagged prompt text."""
        from specweaver.infrastructure.llm.prompt.render import render_blocks

        return render_blocks(blocks, order=self._profile.order)
