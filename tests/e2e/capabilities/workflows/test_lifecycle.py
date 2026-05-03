# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""End-to-end lifecycle test — full SpecWeaver pipeline with mocked LLM.

Exercises the complete spec-driven workflow:
    sw init → sw draft → sw check (spec) → sw review (spec)
    → sw implement → sw check (code) → sw review (code)

The LLM is mocked so this test is deterministic, free, and CI-friendly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse
from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

# Counter for unique project names in tests
_proj_counter = 0


def _unique_name(prefix: str = "test") -> str:
    """Generate unique project names to avoid DB collisions."""
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


_DRAFT_SECTION_RESPONSES = [
    # Purpose
    (
        "The `greet_service` module provides a single function `greet(name)` "
        "that returns a personalized greeting string."
    ),
    # Contract
    (
        "### Interface\n\n"
        "```python\n"
        "def greet(name: str) -> str:\n"
        '    """Return a greeting for the given name."""\n'
        "```\n\n"
        "### Examples\n\n"
        "```python\n"
        '>>> greet("Alice")\n'
        '"Hello, Alice!"\n'
        '>>> greet("")\n'
        '"Hello, World!"\n'
        "```"
    ),
    # Protocol
    (
        "1. Accept a `name` parameter of type `str`.\n"
        '2. If `name` is empty or whitespace-only, use `"World"` as default.\n'
        '3. Return the string `"Hello, {name}!"`.'
    ),
    # Policy
    (
        "### Error Handling\n\n"
        "| Error Condition | Behavior |\n"
        "|---|---|\n"
        "| `name` is not a string | Raise `TypeError` |\n"
        "| `name` is `None` | Raise `TypeError` |\n\n"
        "### Limits\n\n"
        "| Parameter | Default | Range |\n"
        "|---|---|---|\n"
        "| `name` length | N/A | 1-100 characters |"
    ),
    # Boundaries
    (
        "| Concern | Owned By |\n"
        "|---|---|\n"
        "| Input validation beyond type | Caller |\n"
        "| Internationalization | Not in scope |\n"
        "| Logging | Infrastructure layer |"
    ),
]

# Review: spec review response (ACCEPTED)
_SPEC_REVIEW_RESPONSE = (
    "VERDICT: ACCEPTED\n"
    "- Clear single responsibility\n"
    "- Concrete examples provided\n"
    "- Error paths defined\n"
    "The spec is well-structured and implementable."
)

# Implement: generated code
_GENERATED_CODE = '''\
"""Greet service — personalized greeting generator."""


def greet(name: str) -> str:
    """Return a greeting for the given name.

    Args:
        name: The name to greet. If empty, defaults to "World".

    Returns:
        A greeting string.

    Raises:
        TypeError: If name is not a string.
    """
    if not isinstance(name, str):
        msg = f"Expected str, got {type(name).__name__}"
        raise TypeError(msg)

    name = name.strip()
    if not name:
        name = "World"

    return f"Hello, {name}!"
'''

# Implement: generated tests
_GENERATED_TESTS = '''\
"""Tests for greet_service."""

from greet_service import greet


class TestGreetHappyPath:
    """Happy path tests."""

    def test_greet_with_name(self) -> None:
        assert greet("Alice") == "Hello, Alice!"

    def test_greet_with_empty_string(self) -> None:
        assert greet("") == "Hello, World!"


class TestGreetEdgeCases:
    """Edge case tests."""

    def test_greet_whitespace_only(self) -> None:
        assert greet("   ") == "Hello, World!"
'''

# Review: code review response (ACCEPTED)
_CODE_REVIEW_RESPONSE = (
    "VERDICT: ACCEPTED\n"
    "- Code matches spec contract\n"
    "- Error handling implemented correctly\n"
    "- Type hints present on public function\n"
    "The implementation is correct and complete."
)


# ---------------------------------------------------------------------------
# Helper: create a mock LLM adapter with sequenced responses
# ---------------------------------------------------------------------------


def _make_sequenced_llm(responses: list[str]) -> object:
    """Create a mock LLM that returns responses in sequence."""
    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"
    captured_prompts = []

    response_iter = iter(responses)

    async def _generate(
        messages: object,
        config: object = None,
        dispatcher: object = None,
        on_tool_round: object = None,
    ) -> LLMResponse:
        for msg in messages:
            if hasattr(msg, "content"):
                captured_prompts.append(msg.content)

        try:
            text = next(response_iter)
        except StopIteration:
            text = "VERDICT: ACCEPTED\nEnd of mocked responses."

        return LLMResponse(text=text, model="mock")

    mock_llm.generate = _generate
    mock_llm.generate_with_tools = _generate
    return mock_llm


# ---------------------------------------------------------------------------
# E2E Lifecycle Test
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """End-to-end test of the complete SpecWeaver pipeline."""

    def test_init_creates_project(self, tmp_path: Path) -> None:
        """Step 1: sw init scaffolds the project structure."""
        result = runner.invoke(app, ["init", "myapp", "--path", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / ".specweaver").is_dir()
        assert (tmp_path / "specs").is_dir()
        assert (tmp_path / "CONSTITUTION.md").is_file()
        assert (tmp_path / "src" / "context.yaml").is_file()
        assert (tmp_path / "tests" / "context.yaml").is_file()

    def test_full_pipeline(self, tmp_path: Path) -> None:
        """Full lifecycle: init → draft → check → review → implement → check → review."""
        # -- Step 1: Init --------------------------------------------------
        result = runner.invoke(app, ["init", "fullpipe", "--path", str(tmp_path)])
        assert result.exit_code == 0, f"init failed: {result.output}"

        # -- Step 2: Draft (mocked LLM + mocked HITL) ----------------------
        draft_llm = _make_sequenced_llm(_DRAFT_SECTION_RESPONSES)

        # Mock HITL provider to return predefined answers
        _mock_hitl_answers = iter(
            [
                "Returns a greeting for a given name",  # Purpose
                "greet(name: str) -> str",  # Contract
                "Accept name, default empty to World, format greeting",  # Protocol
                "TypeError if name is not a string",  # Policy
                "Internationalization is out of scope",  # Boundaries
            ]
        )

        async def _mock_ask(question: str, *, section: str = "") -> str:
            return next(_mock_hitl_answers, "")

        with (
            patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req,
            patch(
                "specweaver.workspace.context.hitl_provider.HITLProvider",
            ) as mock_hitl_cls,
        ):
            mock_req.return_value = (
                None,  # settings
                draft_llm,
                GenerationConfig(model="mock"),
            )
            mock_hitl_instance = AsyncMock()
            mock_hitl_instance.ask = _mock_ask
            mock_hitl_instance.name = "mock_hitl"
            mock_hitl_cls.return_value = mock_hitl_instance

            result = runner.invoke(
                app,
                ["draft", "greet_service", "--project", str(tmp_path)],
            )
            assert result.exit_code == 0, f"draft failed: {result.output}"

        spec_path = tmp_path / "specs" / "greet_service_spec.md"
        assert spec_path.exists(), "Spec file was not created"
        spec_content = spec_path.read_text(encoding="utf-8")
        assert "greet" in spec_content.lower()

        # -- Step 3: Check spec (fully local, no mock needed) ---------------
        result = runner.invoke(
            app,
            [
                "check",
                str(spec_path),
                "--level",
                "component",
                "--project",
                str(tmp_path),
            ],
        )
        # Spec might not pass all rules, but the command should run
        assert result.exit_code in (0, 1), f"check spec crashed: {result.output}"
        assert "S01" in result.output  # Shows rule IDs

        # -- Step 4: Review spec (mocked LLM) ------------------------------
        review_llm = _make_sequenced_llm([_SPEC_REVIEW_RESPONSE])

        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                review_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                [
                    "review",
                    str(spec_path),
                    "--project",
                    str(tmp_path),
                ],
            )
            assert result.exit_code == 0, f"review spec failed: {result.output}"
            assert "ACCEPTED" in result.output

        # -- Step 5: Implement (mocked LLM) --------------------------------
        impl_llm = _make_sequenced_llm([_GENERATED_CODE, _GENERATED_TESTS])

        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                impl_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                [
                    "implement",
                    str(spec_path),
                    "--project",
                    str(tmp_path),
                ],
            )
            assert result.exit_code == 0, f"implement failed: {result.output}"

        code_path = tmp_path / "src" / "greet_service.py"
        test_path = tmp_path / "tests" / "test_greet_service.py"
        assert code_path.exists(), "Code file was not generated"
        assert test_path.exists(), "Test file was not generated"

        code_content = code_path.read_text(encoding="utf-8")
        assert "def greet" in code_content

        # -- Step 6: Check code (fully local, no mock needed) ---------------
        result = runner.invoke(
            app,
            [
                "check",
                str(code_path),
                "--level",
                "code",
                "--project",
                str(tmp_path),
            ],
        )
        assert result.exit_code in (0, 1), f"check code crashed: {result.output}"
        assert "C01" in result.output  # Shows code rule IDs

        # -- Step 7: Review code (mocked LLM) ------------------------------
        code_review_llm = _make_sequenced_llm([_CODE_REVIEW_RESPONSE])

        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                code_review_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                [
                    "review",
                    str(code_path),
                    "--spec",
                    str(spec_path),
                    "--project",
                    str(tmp_path),
                ],
            )
            assert result.exit_code == 0, f"review code failed: {result.output}"
            assert "ACCEPTED" in result.output


class TestLifecycleEdgeCases:
    """Edge cases for the lifecycle pipeline."""

    def test_draft_existing_spec_blocked(self, tmp_path: Path) -> None:
        """Draft refuses to overwrite an existing spec file."""
        runner.invoke(app, ["init", _unique_name("draft"), "--path", str(tmp_path)])

        # Create a spec file manually
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir(exist_ok=True)
        (specs_dir / "existing_spec.md").write_text("# Existing", encoding="utf-8")

        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                _make_sequenced_llm([]),
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["draft", "existing", "--project", str(tmp_path)],
            )
            assert result.exit_code != 0
            assert "already exists" in result.output.lower()

    def test_implement_nonexistent_spec_fails(self) -> None:
        """Implement with missing spec file → exit code 1."""
        result = runner.invoke(
            app,
            ["implement", "/nonexistent/spec.md"],
        )
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "error" in result.output.lower()

    def test_review_denied_exits_with_error(self, tmp_path: Path) -> None:
        """Review that returns DENIED → exit code 1."""
        runner.invoke(app, ["init", _unique_name("review"), "--path", str(tmp_path)])

        spec = tmp_path / "specs" / "bad_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Bad spec\n\nNo details.", encoding="utf-8")

        denied_llm = _make_sequenced_llm(
            [
                "VERDICT: DENIED\n- Missing examples\n- No error paths\nReject.",
            ]
        )

        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                denied_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["review", str(spec), "--project", str(tmp_path)],
            )
            assert result.exit_code == 1
            assert "DENIED" in result.output

    def test_check_invalid_level_fails(self, tmp_path: Path) -> None:
        """Check with invalid level → error message."""
        spec = tmp_path / "test.md"
        spec.write_text("# Test", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", str(spec), "--level", "invalid"],
        )
        assert result.exit_code != 0
