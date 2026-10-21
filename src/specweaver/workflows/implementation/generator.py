# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Code generator — LLM-driven code and test generation from specs.

Reads a validated component spec and generates:
1. Implementation source file(s)
2. Test file(s) covering spec Contract examples and Policy error cases
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role
from specweaver.workflows.implementation.languages import LanguageGuide, language_guide

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


def generation_prompt(
    spec_path: Path,
    base_prompt: PromptBuilder,
    *,
    artifact_uuid: str | None = None,
    dictator_overrides: list[str] | None = None,
    validation_findings: str | None = None,
    environment_context: str | None = None,
    language: str = "python",
    brief: str | None = None,
) -> str:
    """The prompt code or tests are generated from: the base, the spec, and what the run adds.

    One-shot and agentic generation build it the same way, so both tag the file for lineage in the
    language's comment syntax. The brief comes after the instructions, so the prompt's start stays
    the same from task to task.
    """
    if artifact_uuid:
        base_prompt.add_artifact_tagging(artifact_uuid, language)
    base_prompt.add_file(spec_path, priority=1, role="reference")
    if brief:
        base_prompt.add_context(brief, "task_files", priority=1)
    if dictator_overrides:
        base_prompt.add_dictator_overrides(dictator_overrides)
    if validation_findings:
        base_prompt.add_context(validation_findings, "validation_errors", priority=2)
    if environment_context:
        base_prompt.add_context(environment_context, "environment_context")
        logger.debug("generation prompt: MCP env injected (%d chars)", len(environment_context))
    return base_prompt.build()


class Generator:
    """LLM-driven code and test generator from specs."""

    def __init__(
        self,
        llm: LLMAdapter,
        config: GenerationConfig,
        guide: LanguageGuide | None = None,
    ) -> None:
        self._llm = llm
        self._config = config
        self._guide = guide or language_guide("python")

    async def generate_code(
        self, spec_path: Path, output_path: Path, base_prompt: PromptBuilder, **parts: Any
    ) -> Path:
        """Write the implementation `output_path` from the spec; `parts` are `generation_prompt`'s
        keyword arguments (the lineage id, overrides, findings, environment, language, brief)."""
        return await self._write(
            self._guide.code_role, spec_path, output_path, base_prompt, "generate_code", parts
        )

    async def generate_tests(
        self, spec_path: Path, output_path: Path, base_prompt: PromptBuilder, **parts: Any
    ) -> Path:
        """Write the test file `output_path` from the spec; `parts` as for `generate_code`."""
        return await self._write(
            self._guide.tests_role, spec_path, output_path, base_prompt, "generate_tests", parts
        )

    async def _write(
        self,
        role: str,
        spec_path: Path,
        output_path: Path,
        base_prompt: PromptBuilder,
        label: str,
        parts: dict[str, Any],
    ) -> Path:
        prompt = generation_prompt(spec_path, base_prompt, **parts)
        messages = [
            Message(role=Role.SYSTEM, content=role),
            Message(role=Role.USER, content=prompt),
        ]
        logger.info("%s: generating from %s", label, spec_path)
        response = await self._llm.generate(messages, self._config)
        code = strip_fences(response.text)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        logger.info("%s: wrote %d bytes to %s", label, len(code), output_path)
        return output_path


def strip_fences(text: str) -> str:
    """The code without the fence a model wrapped it in, whatever its info string.

    Only the first and the last line can be the fence: one inside the code (a raw string, a doc
    comment) is code.
    """
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip() + "\n"
