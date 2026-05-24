# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Mixin class containing add methods for PromptBuilder."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.assurance.graph.topology import TopologyContext
    from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention
    from specweaver.infrastructure.llm.models import ProjectMetadata
    from specweaver.infrastructure.llm.prompt.builder import PromptBuilder

from specweaver.infrastructure.llm.escaping import apply_escaping
from specweaver.infrastructure.llm.prompt.block import _ContentBlock
from specweaver.infrastructure.llm.prompt.constants import _CONSTITUTION_PREAMBLE, detect_language
from specweaver.infrastructure.llm.prompt.profiles import PromptSlot

logger = logging.getLogger(__name__)


class PromptBuilderAddersMixin:
    """Mixin class for adding content blocks to PromptBuilder."""

    # Stub attributes and methods to satisfy mypy type checking
    _blocks: list[_ContentBlock]
    _skeleton_files: dict[str, str]

    def _is_slot_active(self, slot: Any) -> bool:
        return False

    def _count(self, text: str) -> int:
        return 0

    def add_instructions(self, text: str, *, escaping: str | None = None) -> PromptBuilder:
        """Add instruction text (priority 0 — never truncated).

        Instructions are placed at the top of the prompt inside
        ``<instructions>`` tags.
        """
        if not self._is_slot_active(PromptSlot.INSTRUCTIONS):
            logger.debug("Slot %s inactive — skipping add_instructions", PromptSlot.INSTRUCTIONS)
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "raw"
        apply_escaping("", actual_escaping)

        tokens = self._count(apply_escaping(text, actual_escaping))
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=0,
                kind="instructions",
                tokens=tokens,
                escaping=actual_escaping,
            ),
        )
        return self  # type: ignore[return-value]

    def add_dictator_overrides(
        self, overrides: list[str], *, escaping: str | None = None
    ) -> PromptBuilder:
        """Add human-in-the-loop dictator override blocks (priority 0 — never truncated).

        Overrides are placed inside ``<dictator-overrides>`` tags.
        """
        if not overrides:
            return self  # type: ignore[return-value]

        if not self._is_slot_active(PromptSlot.DICTATOR_OVERRIDES):
            logger.debug(
                "Slot %s inactive — skipping add_dictator_overrides", PromptSlot.DICTATOR_OVERRIDES
            )
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "raw"
        apply_escaping("", actual_escaping)

        lines = [f"- {o}" for o in overrides]
        text_block = "\n".join(lines)

        tokens = self._count(apply_escaping(text_block, actual_escaping))
        self._blocks.append(
            _ContentBlock(
                text=text_block,
                priority=0,
                kind="dictator-overrides",
                label="dictator-overrides",
                tokens=tokens,
                escaping=actual_escaping,
            ),
        )
        return self  # type: ignore[return-value]

    def add_context(
        self,
        text: Any,
        label: str = "",
        *,
        priority: int = 3,
        slot: PromptSlot = PromptSlot.CONTEXT,
        **kwargs: Any,
    ) -> PromptBuilder:
        """Add any context source implementing PromptContentSource or a legacy string context."""
        if isinstance(text, str):
            # It's a legacy string context
            return self.add_string_context(
                content=text,
                label=label,
                priority=priority,
                slot=slot,
                escaping=kwargs.get("escaping"),
            )
        elif hasattr(text, "get_prompt_content") and hasattr(text, "get_prompt_label"):
            # It's an adapter source
            source = text
            # Extract slots / priority from kwargs if present, else use default
            prio = kwargs.get("priority", priority)
            actual_slot = kwargs.get("slot", slot)

            if not self._is_slot_active(actual_slot):
                return self  # type: ignore[return-value]

            content = source.get_prompt_content()
            tokens = self._count(content)

            self._blocks.append(
                _ContentBlock(
                    text=content,
                    priority=max(1, prio),
                    kind=actual_slot.value,
                    label=source.get_prompt_label(),
                    tokens=tokens,
                    escaping="raw",
                    source=source,
                )
            )
            return self  # type: ignore[return-value]
        else:
            raise TypeError("Source must conform to PromptContentSource protocol")

    def add_string_context(
        self,
        content: str,
        label: str,
        *,
        priority: int = 3,
        slot: PromptSlot = PromptSlot.CONTEXT,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Add raw string context wrapped in StringPromptAdapter."""
        from specweaver.infrastructure.llm.prompt.adapter import StringPromptAdapter

        actual_escaping = escaping if escaping is not None else "cdata"
        adapter = StringPromptAdapter(content, label, escaping=actual_escaping)
        return self.add_context(adapter, priority=priority, slot=slot)

    def add_file_context(
        self,
        path: Path,
        *,
        priority: int = 2,
        label: str = "",
        role: str = "",
        skeleton: bool = False,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Add file context wrapped in FilePromptAdapter."""
        from specweaver.infrastructure.llm.prompt.adapter import FilePromptAdapter

        actual_escaping = escaping if escaping is not None else "cdata"
        adapter = FilePromptAdapter(
            path,
            label=label,
            role=role,
            escaping=actual_escaping,
            skeleton=skeleton,
            skeleton_files=self._skeleton_files,
        )
        return self.add_context(adapter, priority=priority, slot=PromptSlot.FILE)

    def add_project_metadata_context(
        self,
        metadata: ProjectMetadata | None,
        *,
        priority: int = 1,
    ) -> PromptBuilder:
        """Add project metadata wrapped in ProjectMetadataPromptAdapter."""
        if not metadata:
            return self  # type: ignore[return-value]
        from specweaver.infrastructure.llm.prompt.adapter import ProjectMetadataPromptAdapter

        adapter = ProjectMetadataPromptAdapter(metadata)
        return self.add_context(adapter, priority=priority, slot=PromptSlot.METADATA)

    def add_file(
        self,
        path: Path,
        *,
        priority: int = 2,
        label: str = "",
        role: str = "",
        skeleton: bool = False,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Legacy delegate for add_file_context."""
        return self.add_file_context(
            path,
            priority=priority,
            label=label,
            role=role,
            skeleton=skeleton,
            escaping=escaping,
        )

    def add_project_metadata(
        self,
        metadata: ProjectMetadata | None,
        *,
        priority: int = 1,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Legacy delegate for add_project_metadata_context."""
        # Note: escaping parameter is ignored as ProjectMetadataPromptAdapter handles its own JSON serialization
        return self.add_project_metadata_context(metadata, priority=priority)

    def add_topology(
        self,
        contexts: list[TopologyContext],
        *,
        priority: int = 2,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Add topology context rendered as ``<topology>`` XML.

        Args:
            contexts: List of ``TopologyContext`` from
                ``TopologyGraph.format_context_summary()``.
            priority: Truncation priority.  Default 2.
            escaping: Optional escaping strategy. Defaults to "raw".
        """
        if not contexts:
            return self  # type: ignore[return-value]

        if not self._is_slot_active(PromptSlot.TOPOLOGY):
            logger.debug("Slot %s inactive — skipping add_topology", PromptSlot.TOPOLOGY)
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "raw"
        apply_escaping("", actual_escaping)

        lines: list[str] = []
        for ctx in contexts:
            constraints_str = ", ".join(ctx.constraints) if ctx.constraints else "none"
            lines.append(
                f"  - {ctx.name} ({ctx.relationship}): "
                f"{ctx.purpose} [archetype={ctx.archetype}, "
                f"constraints={constraints_str}]"
            )
        text = "\n".join(lines)
        tokens = self._count(apply_escaping(text, actual_escaping))
        self._blocks.append(
            _ContentBlock(
                text=text,
                priority=max(1, priority),
                kind="topology",
                label="topology",
                tokens=tokens,
                escaping=actual_escaping,
            ),
        )
        return self  # type: ignore[return-value]

    def add_reminder(self, text: str, *, escaping: str | None = None) -> PromptBuilder:
        """Add a reminder block rendered at the bottom of the prompt.

        Reminders are placed after all other content to reinforce
        critical instructions.  Priority 0 — never truncated.
        """
        if not self._is_slot_active(PromptSlot.REMINDER):
            logger.debug("Slot %s inactive — skipping add_reminder", PromptSlot.REMINDER)
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "raw"
        apply_escaping("", actual_escaping)

        tokens = self._count(apply_escaping(text, actual_escaping))
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=0,
                kind="reminder",
                tokens=tokens,
                escaping=actual_escaping,
            ),
        )
        return self  # type: ignore[return-value]

    def add_constitution(self, text: str, *, escaping: str | None = None) -> PromptBuilder:
        """Add constitution text (priority 0 — never truncated).

        Constitution is rendered after instructions and before topology,
        inside ``<constitution>`` tags with a fixed preamble.
        """
        if not self._is_slot_active(PromptSlot.CONSTITUTION):
            logger.debug("Slot %s inactive — skipping add_constitution", PromptSlot.CONSTITUTION)
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "raw"
        apply_escaping("", actual_escaping)

        full_text = f"{_CONSTITUTION_PREAMBLE}\n\n{text.strip()}"
        tokens = self._count(apply_escaping(full_text, actual_escaping))
        self._blocks.append(
            _ContentBlock(
                text=full_text,
                priority=0,
                kind="constitution",
                tokens=tokens,
                escaping=actual_escaping,
            ),
        )
        return self  # type: ignore[return-value]

    def add_standards(self, text: str, *, escaping: str | None = None) -> PromptBuilder:
        """Add project standards (priority 1 — truncatable).

        Standards are rendered after constitution, before topology,
        inside ``<standards>`` tags.
        """
        if not self._is_slot_active(PromptSlot.STANDARDS):
            logger.debug("Slot %s inactive — skipping add_standards", PromptSlot.STANDARDS)
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "raw"
        apply_escaping("", actual_escaping)

        tokens = self._count(apply_escaping(text, actual_escaping))
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=1,
                kind="standards",
                tokens=tokens,
                escaping=actual_escaping,
            ),
        )
        return self  # type: ignore[return-value]

    def add_plan(self, text: str, *, escaping: str | None = None) -> PromptBuilder:
        """Add implementation plan context (priority 1 — truncatable).

        Plan content is rendered after standards, before topology,
        inside ``<plan>`` tags.  The caller is responsible for
        selective section extraction (file_layout, architecture,
        tasks, test_expectations) from the full Plan YAML.
        """
        if not self._is_slot_active(PromptSlot.PLAN):
            logger.debug("Slot %s inactive — skipping add_plan", PromptSlot.PLAN)
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "raw"
        apply_escaping("", actual_escaping)

        tokens = self._count(apply_escaping(text, actual_escaping))
        self._blocks.append(
            _ContentBlock(
                text=text.strip(),
                priority=1,
                kind="plan",
                tokens=tokens,
                escaping=actual_escaping,
            ),
        )
        return self  # type: ignore[return-value]

    def add_mentioned_files(
        self,
        mentions: list[ResolvedMention],
        *,
        max_files: int = 5,
        skeleton: bool = True,
        escaping: str | None = None,
    ) -> PromptBuilder:
        """Add auto-detected file mentions from LLM responses.

        Files are added at priority 4 (below explicit files, context,
        standards, and topology — first to be truncated).  Duplicates
        against previously added files are skipped.

        Args:
            mentions: Resolved file mentions from the mention scanner.
            max_files: Maximum number of mentioned files to add.  Default 5.
            skeleton: By default, mentioned referenced files are massively
                condensed via AST boundaries to avoid inflating token constraints.
            escaping: Optional escaping strategy. Defaults to "cdata".
        """
        if not mentions:
            return self  # type: ignore[return-value]

        if not self._is_slot_active(PromptSlot.MENTIONED):
            logger.debug("Slot %s inactive — skipping add_mentioned_files", PromptSlot.MENTIONED)
            return self  # type: ignore[return-value]

        actual_escaping = escaping if escaping is not None else "cdata"
        apply_escaping("", actual_escaping)

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

            if skeleton:
                # Flow engine pre-evaluates and caches bounds
                if path_str in self._skeleton_files:
                    content = self._skeleton_files[path_str]
                else:
                    try:
                        from specweaver.infrastructure.llm._skeleton import extract_ast_skeleton

                        content = extract_ast_skeleton(mention.resolved_path, content)
                    except ImportError:
                        pass

            tokens = self._count(apply_escaping(content, actual_escaping))
            self._blocks.append(
                _ContentBlock(
                    text=content,
                    priority=4,
                    kind="mentioned",
                    label=f"[auto] {mention.resolved_path.name}",
                    language=lang,
                    file_path=path_str,
                    role="reference",
                    tokens=tokens,
                    escaping=actual_escaping,
                ),
            )
            existing_paths.add(path_str)
            added += 1
        return self  # type: ignore[return-value]

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
        from specweaver.infrastructure.llm.lineage import wrap_artifact_tag

        tag = wrap_artifact_tag(artifact_id, language)
        if tag is not None:
            self.add_instructions(
                f"You MUST include the exact string '{tag}' physically at the very top of your output file."
            )
        return self  # type: ignore[return-value]
