# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Code generator — LLM-driven code and test generation from specs.

Reads a validated component spec and generates:
1. Implementation source file(s)
2. Test file(s) covering spec Contract examples and Policy error cases
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.llm.models import GenerationConfig, Message, Role

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.graph.topology import TopologyContext
    from specweaver.llm.adapters.base import LLMAdapter

# Instruction constants — extracted for reuse and testability
CODE_GEN_INSTRUCTIONS = """\
You are a Python code generator. You are implementing a component from its specification.

## Requirements:
1. Implement ALL functions/classes described in the Contract section.
2. Handle ALL error cases from the Policy section.
3. Follow the Protocol section step by step.
4. Include proper type hints on all public methods.
5. Include docstrings for all public methods.
6. Do NOT add functionality not described in the spec.

## Output:
Produce ONLY valid Python code. No markdown fences, no explanation.
Start with imports, then data models, then the main implementation.
Include a module docstring."""

TEST_GEN_INSTRUCTIONS = """\
You are a Python test generator. You are writing tests for a component from its specification.

## Requirements:
1. Write tests using pytest.
2. Cover ALL examples from the Contract section as test cases.
3. Cover ALL error cases from the Policy section.
4. Cover edge cases (empty input, None, boundary values).
5. Use descriptive test names (test_<scenario>).
6. Group tests in classes by concern.

## Output:
Produce ONLY valid Python code. No markdown fences, no explanation.
Start with imports, then test classes with test methods."""


class Generator:
    """LLM-driven code and test generator from specs."""

    def __init__(
        self,
        llm: LLMAdapter,
        config: GenerationConfig | None = None,
    ) -> None:
        self._llm = llm
        self._config = config or GenerationConfig(
            model="gemini-2.5-flash",
            temperature=0.2,  # Low temperature for deterministic code
        )

    async def generate_code(
        self,
        spec_path: Path,
        output_path: Path,
        *,
        topology_contexts: list[TopologyContext] | None = None,
    ) -> Path:
        """Generate implementation code from a spec.

        Args:
            spec_path: Path to the validated spec file.
            output_path: Path to write the generated code to.
            topology_contexts: Optional topology context from the project graph.

        Returns:
            Path to the generated code file.
        """
        from specweaver.llm.prompt_builder import PromptBuilder

        builder = (
            PromptBuilder()
            .add_instructions(CODE_GEN_INSTRUCTIONS)
            .add_file(spec_path, priority=1, role="reference")
        )
        if topology_contexts:
            builder.add_topology(topology_contexts)
        prompt = builder.build()

        messages = [
            Message(
                role=Role.SYSTEM,
                content="You are a precise Python code generator. Output only valid Python code.",
            ),
            Message(role=Role.USER, content=prompt),
        ]

        response = await self._llm.generate(messages, self._config)
        code = self._clean_code_output(response.text)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        return output_path

    async def generate_tests(
        self,
        spec_path: Path,
        output_path: Path,
        *,
        topology_contexts: list[TopologyContext] | None = None,
    ) -> Path:
        """Generate test file from a spec.

        Args:
            spec_path: Path to the validated spec file.
            output_path: Path to write the generated test file to.
            topology_contexts: Optional topology context from the project graph.

        Returns:
            Path to the generated test file.
        """
        from specweaver.llm.prompt_builder import PromptBuilder

        builder = (
            PromptBuilder()
            .add_instructions(TEST_GEN_INSTRUCTIONS)
            .add_file(spec_path, priority=1, role="reference")
        )
        if topology_contexts:
            builder.add_topology(topology_contexts)
        prompt = builder.build()

        messages = [
            Message(
                role=Role.SYSTEM,
                content=(
                    "You are a precise Python test generator. "
                    "Output only valid Python code using pytest."
                ),
            ),
            Message(role=Role.USER, content=prompt),
        ]

        response = await self._llm.generate(messages, self._config)
        code = self._clean_code_output(response.text)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code, encoding="utf-8")
        return output_path

    @staticmethod
    def _clean_code_output(text: str) -> str:
        """Remove markdown code fences if the LLM wrapped output in them."""
        text = text.strip()

        # Remove ```python ... ``` wrapper
        if text.startswith("```python"):
            text = text[len("```python") :].strip()
        elif text.startswith("```"):
            text = text[3:].strip()

        if text.endswith("```"):
            text = text[:-3].strip()

        return text + "\n"
