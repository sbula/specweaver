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

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.llm.adapters.base import LLMAdapter
    from specweaver.llm.models import TokenBudget

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".html": "html",
    ".css": "css",
    ".sql": "sql",
    ".sh": "bash",
    ".bash": "bash",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".xml": "xml",
    ".txt": "text",
}


def detect_language(path: Path) -> str:
    """Map a file extension to a language label for code fencing.

    Returns ``"text"`` for unrecognised extensions.
    """
    return _LANG_MAP.get(path.suffix.lower(), "text")


# ---------------------------------------------------------------------------
# Internal content blocks
# ---------------------------------------------------------------------------


@dataclass
class _ContentBlock:
    """A single block of content to include in the prompt."""

    text: str
    priority: int  # 0 = instructions (never truncated), lower = higher priority
    label: str = ""
    kind: str = "context"  # "instructions", "file", "context"
    language: str = "text"
    file_path: str = ""
    tokens: int = 0
    truncated: bool = False


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------


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
    ) -> None:
        self._budget = budget
        self._adapter = adapter
        self._blocks: list[_ContentBlock] = []

    # ------------------------------------------------------------------
    # Builder API (all return self for chaining)
    # ------------------------------------------------------------------

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
    ) -> PromptBuilder:
        """Read a file and add it as a ``<file>`` block.

        Args:
            path: Path to the file to read.
            priority: Truncation priority (lower = kept first).  Default 2.
            label: Optional human label.  Defaults to the file name.
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

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

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

        if self._budget is not None:
            blocks = self._apply_truncation(blocks)

        return self._render(blocks)

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    def _count(self, text: str) -> int:
        """Estimate token count for *text*."""
        if self._adapter is not None:
            return self._adapter.estimate_tokens(text)
        return len(text) // 4

    # ------------------------------------------------------------------
    # Hybrid truncation
    # ------------------------------------------------------------------

    def _apply_truncation(self, blocks: list[_ContentBlock]) -> list[_ContentBlock]:
        """Apply hybrid priority-ordered + proportional truncation."""
        assert self._budget is not None

        limit = self._budget.limit
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
        shares = {
            i: int((b.tokens / total) * available)
            for i, b in enumerate(group)
        }

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

    # ------------------------------------------------------------------
    # XML rendering
    # ------------------------------------------------------------------

    def _render(self, blocks: list[_ContentBlock]) -> str:
        """Render blocks into XML-tagged prompt text."""
        parts: list[str] = []

        # Instructions first
        instructions = [b for b in blocks if b.kind == "instructions"]
        if instructions:
            instr_text = "\n\n".join(b.text for b in instructions)
            parts.append(f"<instructions>\n{instr_text}\n</instructions>")

        # Files
        files = [b for b in blocks if b.kind == "file"]
        if files:
            file_parts: list[str] = []
            for f in files:
                attrs = f'path="{f.label}" language="{f.language}"'
                marker = "\n[truncated]" if f.truncated else ""
                file_parts.append(
                    f"<file {attrs}>\n{f.text}{marker}\n</file>",
                )
            inner = "\n".join(file_parts)
            parts.append(f"<file_contents>\n{inner}\n</file_contents>")

        # Context blocks
        contexts = [b for b in blocks if b.kind == "context"]
        for ctx in contexts:
            marker = "\n[truncated]" if ctx.truncated else ""
            parts.append(
                f'<context label="{ctx.label}">\n{ctx.text}{marker}\n</context>',
            )

        return "\n\n".join(parts)
