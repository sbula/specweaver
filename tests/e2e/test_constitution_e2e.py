# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — constitution flows through CLI to the LLM (Feature 3.2).

Exercises:
    - Constitution injection into review/implement prompts
    - Constitution CLI commands (show, check, init, force)
    - Config set/get-constitution-max-size round-trip
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.cli import app
from specweaver.llm.models import GenerationConfig, LLMResponse

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



_SPEC_REVIEW_RESPONSE = (
    "VERDICT: ACCEPTED\n"
    "- Clear single responsibility\n"
    "- Concrete examples provided\n"
    "- Error paths defined\n"
    "The spec is well-structured and implementable."
)

_CODE_REVIEW_RESPONSE = (
    "VERDICT: ACCEPTED\n"
    "- Code matches spec contract\n"
    "- Error handling implemented correctly\n"
    "- Type hints present on public function\n"
    "The implementation is correct and complete."
)

_GENERATED_CODE = '''\
"""Greet service — personalized greeting generator."""


def greet(name: str) -> str:
    """Return a greeting for the given name."""
    if not isinstance(name, str):
        msg = f"Expected str, got {type(name).__name__}"
        raise TypeError(msg)
    name = name.strip()
    if not name:
        name = "World"
    return f"Hello, {name}!"
'''

_GENERATED_TESTS = '''\
"""Tests for greet_service."""

from greet_service import greet


class TestGreetHappyPath:
    def test_greet_with_name(self) -> None:
        assert greet("Alice") == "Hello, Alice!"
'''


def _make_capturing_llm(
    responses: list[str],
) -> tuple[object, list[str]]:
    """Create a mock LLM that captures all prompts AND returns responses."""
    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"

    captured_prompts: list[str] = []
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
        text = next(response_iter, "VERDICT: ACCEPTED\nAll good.")
        return LLMResponse(text=text, model="mock")

    mock_llm.generate = _generate
    mock_llm.generate_with_tools = _generate
    return mock_llm, captured_prompts


# ---------------------------------------------------------------------------
# E2E Constitution Tests — Feature 3.2
# ---------------------------------------------------------------------------


class TestConstitutionE2E:
    """E2E tests verifying constitution flows through the CLI to the LLM."""

    _CUSTOM_CONSTITUTION = (
        "# Project Constitution\n\n"
        "## Immutable Rules\n\n"
        "- ALL functions MUST have type hints\n"
        "- NO global mutable state\n"
        "- Every module MUST have a docstring\n"
        "- UNIQUE_MARKER_FOR_TEST_VERIFICATION\n"
    )

    def _init_project_with_constitution(
        self,
        tmp_path: Path,
        constitution_content: str | None = None,
    ) -> None:
        """Helper: init project and optionally overwrite constitution."""
        result = runner.invoke(
            app,
            ["init", _unique_name("const"), "--path", str(tmp_path)],
        )
        assert result.exit_code == 0, f"init failed: {result.output}"
        assert (tmp_path / "CONSTITUTION.md").is_file()

        if constitution_content is not None:
            (tmp_path / "CONSTITUTION.md").write_text(
                constitution_content,
                encoding="utf-8",
            )

        # Create a minimal spec for review/implement
        spec_path = tmp_path / "specs" / "widget_spec.md"
        spec_path.write_text(
            "# Widget Spec\n\n"
            "## Purpose\n\nA simple widget.\n\n"
            "## Contract\n\n```python\ndef make_widget() -> str:\n"
            '    """Create a widget."""\n```\n\n'
            "## Protocol\n\n1. Return 'widget'.\n\n"
            "## Policy\n\n| Error | Behavior |\n|---|---|\n"
            "| None | N/A |\n\n"
            "## Boundaries\n\n| Concern | Owned By |\n|---|---|\n"
            "| Styling | Caller |\n",
            encoding="utf-8",
        )

    def test_review_spec_includes_constitution_in_prompt(
        self,
        tmp_path: Path,
    ) -> None:
        """sw review sends constitution content to the LLM prompt."""
        self._init_project_with_constitution(
            tmp_path,
            self._CUSTOM_CONSTITUTION,
        )
        spec_path = tmp_path / "specs" / "widget_spec.md"
        review_llm, captured = _make_capturing_llm([_SPEC_REVIEW_RESPONSE])

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                review_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["review", str(spec_path), "--project", str(tmp_path)],
            )

        assert result.exit_code == 0, f"review failed: {result.output}"
        assert "ACCEPTED" in result.output
        all_prompts = "\n".join(captured)
        assert "UNIQUE_MARKER_FOR_TEST_VERIFICATION" in all_prompts, (
            "Constitution content was NOT found in the LLM prompt. "
            f"Captured {len(captured)} prompt(s)."
        )

    def test_review_code_includes_constitution_in_prompt(
        self,
        tmp_path: Path,
    ) -> None:
        """sw review --spec sends constitution content to the LLM prompt."""
        self._init_project_with_constitution(
            tmp_path,
            self._CUSTOM_CONSTITUTION,
        )
        spec_path = tmp_path / "specs" / "widget_spec.md"

        code_path = tmp_path / "src" / "widget.py"
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(
            'def make_widget() -> str:\n    return "widget"\n',
            encoding="utf-8",
        )

        review_llm, captured = _make_capturing_llm([_CODE_REVIEW_RESPONSE])

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                review_llm,
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
        all_prompts = "\n".join(captured)
        assert "UNIQUE_MARKER_FOR_TEST_VERIFICATION" in all_prompts, (
            "Constitution content was NOT found in code review prompt."
        )

    def test_implement_includes_constitution_in_prompt(
        self,
        tmp_path: Path,
    ) -> None:
        """sw implement sends constitution to both code and test gen prompts."""
        self._init_project_with_constitution(
            tmp_path,
            self._CUSTOM_CONSTITUTION,
        )
        spec_path = tmp_path / "specs" / "widget_spec.md"
        impl_llm, captured = _make_capturing_llm([_GENERATED_CODE, _GENERATED_TESTS])

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                impl_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["implement", str(spec_path), "--project", str(tmp_path)],
            )

        assert result.exit_code == 0, f"implement failed: {result.output}"
        all_prompts = "\n".join(captured)
        marker_count = all_prompts.count("UNIQUE_MARKER_FOR_TEST_VERIFICATION")
        assert marker_count >= 2, (
            f"Expected constitution in both code and test gen prompts, "
            f"but found marker {marker_count} time(s)."
        )

    def test_custom_constitution_overrides_default(
        self,
        tmp_path: Path,
    ) -> None:
        """Custom CONSTITUTION.md content replaces the default template."""
        self._init_project_with_constitution(tmp_path)  # default
        default_content = (tmp_path / "CONSTITUTION.md").read_text(encoding="utf-8")
        assert "UNIQUE_MARKER" not in default_content  # sanity

        (tmp_path / "CONSTITUTION.md").write_text(
            self._CUSTOM_CONSTITUTION,
            encoding="utf-8",
        )
        spec_path = tmp_path / "specs" / "widget_spec.md"
        review_llm, captured = _make_capturing_llm([_SPEC_REVIEW_RESPONSE])

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                review_llm,
                GenerationConfig(model="mock"),
            )
            runner.invoke(
                app,
                ["review", str(spec_path), "--project", str(tmp_path)],
            )

        all_prompts = "\n".join(captured)
        assert "UNIQUE_MARKER_FOR_TEST_VERIFICATION" in all_prompts

    def test_no_constitution_file_means_no_injection(
        self,
        tmp_path: Path,
    ) -> None:
        """When CONSTITUTION.md is removed, no constitution appears in prompt."""
        self._init_project_with_constitution(tmp_path)

        (tmp_path / "CONSTITUTION.md").unlink()
        assert not (tmp_path / "CONSTITUTION.md").exists()

        spec_path = tmp_path / "specs" / "widget_spec.md"
        review_llm, captured = _make_capturing_llm([_SPEC_REVIEW_RESPONSE])

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                review_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["review", str(spec_path), "--project", str(tmp_path)],
            )

        assert result.exit_code == 0, f"review failed: {result.output}"
        all_prompts = "\n".join(captured)
        assert "<constitution>" not in all_prompts.lower(), (
            "Constitution tag found in prompt after CONSTITUTION.md was deleted."
        )


class TestConstitutionCLI:
    """E2E tests for sw constitution show/check/init commands."""

    def test_constitution_show_displays_content(self, tmp_path: Path) -> None:
        """sw constitution show prints the constitution file content."""
        runner.invoke(app, ["init", _unique_name("cshow"), "--path", str(tmp_path)])
        (tmp_path / "CONSTITUTION.md").write_text(
            "# My Rules\n\nRule 1: Be nice.\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["constitution", "show", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0, f"show failed: {result.output}"
        assert "My Rules" in result.output
        assert "Rule 1" in result.output

    def test_constitution_show_no_file(self, tmp_path: Path) -> None:
        """sw constitution show errors when no CONSTITUTION.md exists."""
        runner.invoke(app, ["init", _unique_name("cshownf"), "--path", str(tmp_path)])
        (tmp_path / "CONSTITUTION.md").unlink(missing_ok=True)

        result = runner.invoke(
            app,
            ["constitution", "show", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "No CONSTITUTION.md found" in result.output

    def test_constitution_check_pass(self, tmp_path: Path) -> None:
        """sw constitution check passes for a small constitution file."""
        runner.invoke(app, ["init", _unique_name("cchk"), "--path", str(tmp_path)])

        result = runner.invoke(
            app,
            ["constitution", "check", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0, f"check failed: {result.output}"
        assert "within size limits" in result.output

    def test_constitution_check_fail_oversize(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """sw constitution check fails when file exceeds DB-configured limit."""
        name = _unique_name("cchkfail")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])

        # Set a tiny max size in the DB
        _mock_db.set_active_project(name)
        _mock_db.set_constitution_max_size(name, 10)

        # Write a > 10-byte constitution
        (tmp_path / "CONSTITUTION.md").write_text(
            "This is way too long for 10 bytes.",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["constitution", "check", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "exceeds" in result.output.lower() or "\u2717" in result.output

    def test_constitution_check_no_file(self, tmp_path: Path) -> None:
        """sw constitution check errors when no CONSTITUTION.md exists."""
        runner.invoke(app, ["init", _unique_name("cchknf"), "--path", str(tmp_path)])
        (tmp_path / "CONSTITUTION.md").unlink(missing_ok=True)

        result = runner.invoke(
            app,
            ["constitution", "check", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "No CONSTITUTION.md found" in result.output

    def test_constitution_init_creates_file(self, tmp_path: Path) -> None:
        """sw constitution init creates CONSTITUTION.md."""
        runner.invoke(app, ["init", _unique_name("cinit"), "--path", str(tmp_path)])
        # Delete the one created by sw init
        (tmp_path / "CONSTITUTION.md").unlink()
        assert not (tmp_path / "CONSTITUTION.md").exists()

        result = runner.invoke(
            app,
            ["constitution", "init", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0, f"init failed: {result.output}"
        assert (tmp_path / "CONSTITUTION.md").exists()
        assert "created" in result.output.lower() or "\u2713" in result.output

    def test_constitution_init_refuses_overwrite(self, tmp_path: Path) -> None:
        """sw constitution init refuses to overwrite without --force."""
        runner.invoke(app, ["init", _unique_name("cinitno"), "--path", str(tmp_path)])
        assert (tmp_path / "CONSTITUTION.md").exists()

        result = runner.invoke(
            app,
            ["constitution", "init", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_constitution_init_force_overwrites(self, tmp_path: Path) -> None:
        """sw constitution init --force overwrites existing file."""
        runner.invoke(app, ["init", _unique_name("cinitf"), "--path", str(tmp_path)])
        (tmp_path / "CONSTITUTION.md").write_text(
            "OLD CONTENT",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["constitution", "init", "--force", "--project", str(tmp_path)],
        )
        assert result.exit_code == 0, f"init --force failed: {result.output}"
        content = (tmp_path / "CONSTITUTION.md").read_text(encoding="utf-8")
        assert "OLD CONTENT" not in content

    def test_config_set_get_constitution_max_size(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """sw config set/get-constitution-max-size round-trip."""
        name = _unique_name("cmaxsz")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        # Set
        result = runner.invoke(app, ["config", "set-constitution-max-size", "8192"])
        assert result.exit_code == 0, f"set failed: {result.output}"
        assert "8192" in result.output

        # Get
        result = runner.invoke(app, ["config", "get-constitution-max-size"])
        assert result.exit_code == 0, f"get failed: {result.output}"
        assert "8192" in result.output

    def test_config_set_constitution_max_size_invalid(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """sw config set-constitution-max-size rejects negative values."""
        name = _unique_name("cmaxbad")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        result = runner.invoke(app, ["config", "set-constitution-max-size", "-1"])
        assert result.exit_code != 0, f"Expected failure for negative size, got: {result.output}"
