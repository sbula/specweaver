# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Structured, token-aware prompt builder with XML-tagged output.

Assembles prompts from instructions, files, and context blocks into a
structured XML format.  Supports hybrid truncation (priority-ordered +
proportional redistribution) when a ``TokenBudget`` is provided.

Usage::

    from specweaver.llm.prompt_builder import PromptBuilder

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
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.graph.topology import TopologyContext
    from specweaver.llm.adapters.base import LLMAdapter
    from specweaver.llm.mention_scanner.models import ResolvedMention
    from specweaver.llm.models import ProjectMetadata, TokenBudget

from specweaver.llm._prompt_constants import (
    _CONSTITUTION_PREAMBLE,
    detect_language,
)

logger = logging.getLogger(__name__)

# Internal content blocks


@dataclass
class _ContentBlock:
    """A single block of content to include in the prompt."""

    text: str
    priority: int  # 0 = instructions (never truncated), lower = higher priority
    label: str = ""
    kind: str = (
        "context"  # "instructions", "file", "context", "topology", "standards", "plan", "reminder"
    )
    language: str = "text"
    file_path: str = ""
    role: str = ""  # trust signal: "reference" | "target" | ""
    tokens: int = 0
    truncated: bool = False


# PromptBuilder


class PromptBuilder:
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
    ) -> None:
        self._budget = budget
        self._adapter = adapter
        self._scale = max(0.1, min(budget_scale_factor, 2.0))  # clamp to [0.1, 2.0]
        self._auto_scale = budget_scale_factor == 1.0  # auto-scale when default
        self._blocks: list[_ContentBlock] = []

    # Builder API (all return self for chaining)

    def add_instructions(self, text: str) -> PromptBuilder:
        """Add instruction text (priority 0 — never truncated).

        Instructions are placed at the top of the prompt inside
        ``<instructions>`` tags.
        """
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=0,
                kind="instructions",
                tokens=self._count(text),
            ),
        )
        return self

    def add_file(
        self,
        path: Path,
        *,
        priority: int = 2,
        label: str = "",
        role: str = "",
    ) -> PromptBuilder:
        """Read a file and add it as a ``<file>`` block.

        Args:
            path: Path to the file to read.
            priority: Truncation priority (lower = kept first).  Default 2.
            label: Optional human label.  Defaults to the file name.
            role: Trust signal — ``"reference"`` (read-only context) or
                ``"target"`` (file being reviewed/generated).  Empty = no signal.
        """
        content = path.read_text(encoding="utf-8")
        lang = detect_language(path)
        self._blocks.append(
            _ContentBlock(
                text=content,
                priority=max(1, priority),  # files are always priority >= 1
                kind="file",
                label=label or path.name,
                language=lang,
                file_path=str(path),
                role=role,
                tokens=self._count(content),
            ),
        )
        return self

    def add_context(
        self,
        text: str,
        label: str,
        *,
        priority: int = 3,
    ) -> PromptBuilder:
        """Add an arbitrary context block.

        Args:
            text: The context text.
            label: A descriptive label (e.g. ``"topology_summary"``).
            priority: Truncation priority.  Default 3.
        """
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=max(1, priority),
                kind="context",
                label=label,
                tokens=self._count(text),
            ),
        )
        return self

    def add_project_metadata(
        self,
        metadata: ProjectMetadata | None,
        *,
        priority: int = 1,
    ) -> PromptBuilder:
        """Add project metadata (e.g. environment, safe config).

        Args:
            metadata: The ProjectMetadata DTO (ignored if None).
            priority: Truncation priority. Default 1 (highly preferred).
        """
        if not metadata:
            return self

        import json

        # We masquarade JSON as YAML block to avoid ruamel.yaml stream parsing overhead
        raw_dict = metadata.model_dump()
        yaml_content = f"project_metadata:\n{json.dumps(raw_dict, indent=2)}"

        self._blocks.append(
            _ContentBlock(
                text=yaml_content,
                priority=max(1, priority),
                kind="project_metadata",
                label="project_metadata",
                tokens=self._count(yaml_content),
            ),
        )
        return self

    def add_topology(
        self,
        contexts: list[TopologyContext],
        *,
        priority: int = 2,
    ) -> PromptBuilder:
        """Add topology context rendered as ``<topology>`` XML.

        Args:
            contexts: List of ``TopologyContext`` from
                ``TopologyGraph.format_context_summary()``.
            priority: Truncation priority.  Default 2.
        """
        if not contexts:
            return self

        lines: list[str] = []
        for ctx in contexts:
            constraints_str = ", ".join(ctx.constraints) if ctx.constraints else "none"
            lines.append(
                f"  - {ctx.name} ({ctx.relationship}): "
                f"{ctx.purpose} [archetype={ctx.archetype}, "
                f"constraints={constraints_str}]"
            )
        text = "\n".join(lines)
        self._blocks.append(
            _ContentBlock(
                text=text,
                priority=max(1, priority),
                kind="topology",
                label="topology",
                tokens=self._count(text),
            ),
        )
        return self

    def add_reminder(self, text: str) -> PromptBuilder:
        """Add a reminder block rendered at the bottom of the prompt.

        Reminders are placed after all other content to reinforce
        critical instructions.  Priority 0 — never truncated.
        """
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=0,
                kind="reminder",
                tokens=self._count(text),
            ),
        )
        return self

    def add_constitution(self, text: str) -> PromptBuilder:
        """Add constitution text (priority 0 — never truncated).

        Constitution is rendered after instructions and before topology,
        inside ``<constitution>`` tags with a fixed preamble.
        """
        full_text = f"{_CONSTITUTION_PREAMBLE}\n\n{text.strip()}"
        self._blocks.append(
            _ContentBlock(
                text=full_text,
                priority=0,
                kind="constitution",
                tokens=self._count(full_text),
            ),
        )
        return self

    def add_standards(self, text: str) -> PromptBuilder:
        """Add project standards (priority 1 — truncatable).

        Standards are rendered after constitution, before topology,
        inside ``<standards>`` tags.
        """
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=1,
                kind="standards",
                tokens=self._count(text),
            ),
        )
        return self

    def add_plan(self, text: str) -> PromptBuilder:
        """Add implementation plan context (priority 1 — truncatable).

        Plan content is rendered after standards, before topology,
        inside ``<plan>`` tags.  The caller is responsible for
        selective section extraction (file_layout, architecture,
        tasks, test_expectations) from the full Plan YAML.
        """
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=1,
                kind="plan",
                tokens=self._count(text),
            ),
        )
        return self

    def add_mentioned_files(
        self,
        mentions: list[ResolvedMention],
        *,
        max_files: int = 5,
    ) -> PromptBuilder:
        """Add auto-detected file mentions from LLM responses.

        Files are added at priority 4 (below explicit files, context,
        standards, and topology — first to be truncated).  Duplicates
        against previously added files are skipped.

        Args:
            mentions: Resolved file mentions from the mention scanner.
            max_files: Maximum number of mentioned files to add.  Default 5.
        """
        # Collect paths already in the builder to avoid duplicates
        existing_paths = {block.file_path for block in self._blocks if block.file_path}

        added = 0
        for mention in mentions:
            if added >= max_files:
                break
            path_str = str(mention.resolved_path)
            if path_str in existing_paths:
                continue
            try:
                content = mention.resolved_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            lang = detect_language(mention.resolved_path)
            self._blocks.append(
                _ContentBlock(
                    text=content,
                    priority=4,
                    kind="mentioned",
                    label=f"[auto] {mention.resolved_path.name}",
                    language=lang,
                    file_path=path_str,
                    role="reference",
                    tokens=self._count(content),
                ),
            )
            existing_paths.add(path_str)
            added += 1
        return self

    def add_artifact_tagging(
        self,
        artifact_id: str,
        language: str,
    ) -> PromptBuilder:
        """Inject an artifact lineage tag instruction.

        Formats the artifact ID using the language's native comment syntax
        and instructs the LLM to place it physically at the very top of the output.
        If the language is unsupported, no tag instruction is added.
        """
        from specweaver.llm.lineage import wrap_artifact_tag

        tag = wrap_artifact_tag(artifact_id, language)
        if tag is not None:
            self.add_instructions(
                f"You MUST include the exact string '{tag}' physically at the very top of your output file."
            )
        return self

    # Build

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

    # Auto budget scaling

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

    # Token estimation

    def _count(self, text: str) -> int:
        """Estimate token count for *text*."""
        if self._adapter is not None:
            return self._adapter.estimate_tokens(text)
        return len(text) // 4

    # Hybrid truncation

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
                truncated_text = block.text[:char_limit]
                result.append(
                    _ContentBlock(
                        text=truncated_text,
                        priority=block.priority,
                        kind=block.kind,
                        label=block.label,
                        language=block.language,
                        file_path=block.file_path,
                        tokens=share,
                        truncated=True,
                    ),
                )
            # else: share == 0, block is dropped entirely

        return result

    # XML rendering (delegated to _prompt_render)

    @staticmethod
    def _render_files(blocks: list[_ContentBlock]) -> str | None:
        """Render ``<file_contents>`` XML from file blocks."""
        from specweaver.llm._prompt_render import render_files

        return render_files(blocks)

    def _render(self, blocks: list[_ContentBlock]) -> str:
        """Render blocks into XML-tagged prompt text."""
        from specweaver.llm._prompt_render import render_blocks

        return render_blocks(blocks)
