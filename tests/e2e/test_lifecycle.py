# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

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

from specweaver.cli import app
from specweaver.llm.models import GenerationConfig, LLMResponse

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


# ---------------------------------------------------------------------------
# Realistic mock LLM responses for each pipeline stage
# ---------------------------------------------------------------------------

# Drafter: 5 sections will be generated
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
        'def greet(name: str) -> str:\n'
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
        "2. If `name` is empty or whitespace-only, use `\"World\"` as default.\n"
        "3. Return the string `\"Hello, {name}!\"`."
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

    response_iter = iter(responses)

    async def _generate(messages: object, config: object = None) -> LLMResponse:
        text = next(response_iter, "VERDICT: ACCEPTED\nAll good.")
        return LLMResponse(text=text, model="mock")

    mock_llm.generate = _generate
    return mock_llm


# ---------------------------------------------------------------------------
# E2E Lifecycle Test
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """End-to-end test of the complete SpecWeaver pipeline."""

    def test_init_creates_project(self, tmp_path: Path) -> None:
        """Step 1: sw init scaffolds the project structure."""
        result = runner.invoke(app, ["init", "--project", str(tmp_path)])

        assert result.exit_code == 0
        assert (tmp_path / ".specweaver").is_dir()
        assert (tmp_path / "specs").is_dir()
        assert (tmp_path / ".specweaver" / "config.yaml").is_file()

    def test_full_pipeline(self, tmp_path: Path) -> None:
        """Full lifecycle: init → draft → check → review → implement → check → review."""
        # -- Step 1: Init --------------------------------------------------
        result = runner.invoke(app, ["init", "--project", str(tmp_path)])
        assert result.exit_code == 0, f"init failed: {result.output}"

        # -- Step 2: Draft (mocked LLM + mocked HITL) ----------------------
        draft_llm = _make_sequenced_llm(_DRAFT_SECTION_RESPONSES)

        # Mock HITL provider to return predefined answers
        _mock_hitl_answers = iter([
            "Returns a greeting for a given name",  # Purpose
            "greet(name: str) -> str",  # Contract
            "Accept name, default empty to World, format greeting",  # Protocol
            "TypeError if name is not a string",  # Policy
            "Internationalization is out of scope",  # Boundaries
        ])

        async def _mock_ask(question: str, *, section: str = "") -> str:
            return next(_mock_hitl_answers, "")

        with (
            patch("specweaver.cli._require_llm_adapter") as mock_req,
            patch(
                "specweaver.context.hitl_provider.HITLProvider",
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
                "--level", "component",
                "--project", str(tmp_path),
            ],
        )
        # Spec might not pass all rules, but the command should run
        assert result.exit_code in (0, 1), f"check spec crashed: {result.output}"
        assert "S01" in result.output  # Shows rule IDs

        # -- Step 4: Review spec (mocked LLM) ------------------------------
        review_llm = _make_sequenced_llm([_SPEC_REVIEW_RESPONSE])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
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
                    "--project", str(tmp_path),
                ],
            )
            assert result.exit_code == 0, f"review spec failed: {result.output}"
            assert "ACCEPTED" in result.output

        # -- Step 5: Implement (mocked LLM) --------------------------------
        impl_llm = _make_sequenced_llm([_GENERATED_CODE, _GENERATED_TESTS])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
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
                    "--project", str(tmp_path),
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
                "--level", "code",
                "--project", str(tmp_path),
            ],
        )
        assert result.exit_code in (0, 1), f"check code crashed: {result.output}"
        assert "C01" in result.output  # Shows code rule IDs

        # -- Step 7: Review code (mocked LLM) ------------------------------
        code_review_llm = _make_sequenced_llm([_CODE_REVIEW_RESPONSE])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
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
                    "--spec", str(spec_path),
                    "--project", str(tmp_path),
                ],
            )
            assert result.exit_code == 0, f"review code failed: {result.output}"
            assert "ACCEPTED" in result.output


class TestLifecycleEdgeCases:
    """Edge cases for the lifecycle pipeline."""

    def test_draft_existing_spec_blocked(self, tmp_path: Path) -> None:
        """Draft refuses to overwrite an existing spec file."""
        runner.invoke(app, ["init", "--project", str(tmp_path)])

        # Create a spec file manually
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir(exist_ok=True)
        (specs_dir / "existing_spec.md").write_text("# Existing", encoding="utf-8")

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
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
        runner.invoke(app, ["init", "--project", str(tmp_path)])

        spec = tmp_path / "specs" / "bad_spec.md"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text("# Bad spec\n\nNo details.", encoding="utf-8")

        denied_llm = _make_sequenced_llm([
            "VERDICT: DENIED\n- Missing examples\n- No error paths\nReject.",
        ])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
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


# ---------------------------------------------------------------------------
# High Priority Edge Cases
# ---------------------------------------------------------------------------


class TestHighPriorityEdgeCases:
    """High-priority edge cases that are likely to find real bugs."""

    def _init_and_create_spec(self, tmp_path: Path) -> Path:
        """Helper: init project and create a spec file."""
        runner.invoke(app, ["init", "--project", str(tmp_path)])
        spec_path = tmp_path / "specs" / "greet_service_spec.md"
        spec_path.parent.mkdir(exist_ok=True)
        spec_path.write_text(
            "# greet_service\n\n"
            "## 1. Purpose\n\n"
            "Returns a personalized greeting for a given name.\n\n"
            "## 2. Contract\n\n"
            "```python\n"
            "def greet(name: str) -> str: ...\n"
            "```\n\n"
            "## 3. Protocol\n\n"
            "1. Accept name parameter.\n"
            "2. Return formatted greeting.\n\n"
            "## 4. Policy\n\n"
            "Raise TypeError if name is not a string.\n\n"
            "## 5. Boundaries\n\n"
            "Internationalization is out of scope.\n",
            encoding="utf-8",
        )
        return spec_path

    def test_llm_failure_mid_implement_partial_state(
        self,
        tmp_path: Path,
    ) -> None:
        """LLM succeeds on code gen but fails on test gen → partial state.

        The code file should still exist even if test gen fails.
        """
        spec_path = self._init_and_create_spec(tmp_path)

        call_count = 0

        async def _generate_or_fail(
            messages: object,
            config: object = None,
        ) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: code generation succeeds
                return LLMResponse(text=_GENERATED_CODE, model="mock")
            # Second call: test generation fails
            from specweaver.llm.errors import GenerationError

            msg = "LLM overloaded, try again later"
            raise GenerationError(msg)

        failing_llm = AsyncMock()
        failing_llm.available.return_value = True
        failing_llm.generate = _generate_or_fail

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                failing_llm,
                GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                [
                    "implement",
                    str(spec_path),
                    "--project", str(tmp_path),
                ],
            )
            # Command should fail
            assert result.exit_code != 0

        # Code file from step 1 should still exist (partial state)
        code_path = tmp_path / "src" / "greet_service.py"
        assert code_path.exists(), "Code file should persist after partial failure"

        # Test file should NOT exist (step 2 failed)
        test_path = tmp_path / "tests" / "test_greet_service.py"
        assert not test_path.exists(), "Test file should not exist after LLM failure"

    def test_llm_returns_empty_response(self, tmp_path: Path) -> None:
        """LLM returns empty string during implement → graceful handling."""
        spec_path = self._init_and_create_spec(tmp_path)

        empty_llm = _make_sequenced_llm(["", ""])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                empty_llm,
                GenerationConfig(model="mock"),
            )
            runner.invoke(
                app,
                [
                    "implement",
                    str(spec_path),
                    "--project", str(tmp_path),
                ],
            )

        # Even with empty response, a file gets written (with just a newline)
        code_path = tmp_path / "src" / "greet_service.py"
        if code_path.exists():
            content = code_path.read_text(encoding="utf-8")
            # Empty LLM output → file should be nearly empty
            assert len(content.strip()) == 0

    def test_double_init_preserves_existing_content(
        self,
        tmp_path: Path,
    ) -> None:
        """Init twice → existing specs and config are preserved."""
        # First init
        runner.invoke(app, ["init", "--project", str(tmp_path)])

        # Create a spec file in the project
        spec_path = tmp_path / "specs" / "my_component_spec.md"
        spec_path.write_text("# My important spec", encoding="utf-8")

        # Modify config to verify it's preserved
        config_path = tmp_path / ".specweaver" / "config.yaml"
        original_config = config_path.read_text(encoding="utf-8")

        # Second init
        result = runner.invoke(app, ["init", "--project", str(tmp_path)])
        assert result.exit_code == 0

        # Spec file should still exist with same content
        assert spec_path.exists()
        assert spec_path.read_text(encoding="utf-8") == "# My important spec"

        # Config should not be overwritten
        assert config_path.read_text(encoding="utf-8") == original_config

    def test_spec_to_code_data_integrity(self, tmp_path: Path) -> None:
        """Generated code should contain concepts from the spec."""
        spec_path = self._init_and_create_spec(tmp_path)

        # LLM returns code that references spec concepts
        impl_llm = _make_sequenced_llm([_GENERATED_CODE, _GENERATED_TESTS])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
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
                    "--project", str(tmp_path),
                ],
            )
            assert result.exit_code == 0

        code_path = tmp_path / "src" / "greet_service.py"
        code_content = code_path.read_text(encoding="utf-8")

        # Code should contain key concepts from the spec
        assert "def greet" in code_content, "Function name from spec missing"
        assert "str" in code_content, "Type hint from spec missing"
        assert "TypeError" in code_content, "Error type from spec missing"

        # Test file should reference the implementation
        test_path = tmp_path / "tests" / "test_greet_service.py"
        test_content = test_path.read_text(encoding="utf-8")
        assert "greet" in test_content, "Tests should reference the greet function"


# ---------------------------------------------------------------------------
# Medium Priority Edge Cases
# ---------------------------------------------------------------------------


class TestMediumPriorityEdgeCases:
    """Medium-priority edge cases for resilience and security."""

    def _init_project(self, tmp_path: Path) -> None:
        """Helper: init a project."""
        runner.invoke(app, ["init", "--project", str(tmp_path)])

    def test_path_traversal_in_component_name(self, tmp_path: Path) -> None:
        """Path traversal in component name should be contained to specs dir."""
        self._init_project(tmp_path)

        traversal_name = "../../etc/passwd"

        draft_llm = _make_sequenced_llm(_DRAFT_SECTION_RESPONSES)
        mock_hitl = AsyncMock()
        mock_hitl.ask = AsyncMock(return_value="test answer")
        mock_hitl.name = "mock_hitl"

        with (
            patch("specweaver.cli._require_llm_adapter") as mock_req,
            patch(
                "specweaver.context.hitl_provider.HITLProvider",
            ) as mock_hitl_cls,
        ):
            mock_req.return_value = (
                None,
                draft_llm,
                GenerationConfig(model="mock"),
            )
            mock_hitl_cls.return_value = mock_hitl

            result = runner.invoke(
                app,
                ["draft", traversal_name, "--project", str(tmp_path)],
            )

        # Either should fail gracefully OR the file should land inside specs/
        if result.exit_code == 0:
            # If it succeeded, verify no file escaped the specs directory
            specs_dir = tmp_path / "specs"
            # The file with the traversal name should only exist under specs/
            import os

            for dirpath, _dirnames, filenames in os.walk(tmp_path):
                for f in filenames:
                    if f.endswith("_spec.md"):
                        full = os.path.join(dirpath, f)
                        assert full.startswith(
                            str(specs_dir),
                        ), f"Spec file escaped specs dir: {full}"

    def test_implement_after_denied_review(self, tmp_path: Path) -> None:
        """User ignores DENIED review and implements anyway → should work."""
        self._init_project(tmp_path)

        # Create a spec
        spec_path = tmp_path / "specs" / "risky_spec.md"
        spec_path.parent.mkdir(exist_ok=True)
        spec_path.write_text(
            "# risky_module\n\n## 1. Purpose\n\nDoes risky things.\n",
            encoding="utf-8",
        )

        # Step 1: Review → DENIED
        denied_llm = _make_sequenced_llm([
            "VERDICT: DENIED\n- Insufficient detail\n- Missing error paths",
        ])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                denied_llm,
                GenerationConfig(model="mock"),
            )
            review_result = runner.invoke(
                app,
                ["review", str(spec_path), "--project", str(tmp_path)],
            )
            assert review_result.exit_code == 1
            assert "DENIED" in review_result.output

        # Step 2: Implement anyway (user's choice, no gate enforcement)
        impl_llm = _make_sequenced_llm([_GENERATED_CODE, _GENERATED_TESTS])

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None,
                impl_llm,
                GenerationConfig(model="mock"),
            )
            impl_result = runner.invoke(
                app,
                [
                    "implement",
                    str(spec_path),
                    "--project", str(tmp_path),
                ],
            )
            # Implement should still work — review is advisory
            assert impl_result.exit_code == 0

        code_path = tmp_path / "src" / "risky.py"
        assert code_path.exists()

    def test_multiple_components_no_cross_contamination(
        self,
        tmp_path: Path,
    ) -> None:
        """Draft + implement two components → files are independent."""
        self._init_project(tmp_path)

        # --- Component A: greet_service ---
        spec_a = tmp_path / "specs" / "comp_a_spec.md"
        spec_a.parent.mkdir(exist_ok=True)
        spec_a.write_text(
            "# comp_a\n\n## 1. Purpose\n\nComponent A does X.\n",
            encoding="utf-8",
        )

        code_a = '"""Component A."""\n\ndef do_x() -> str:\n    return "X"\n'
        tests_a = '"""Tests for comp_a."""\n\ndef test_do_x() -> None:\n    pass\n'

        llm_a = _make_sequenced_llm([code_a, tests_a])
        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None, llm_a, GenerationConfig(model="mock"),
            )
            result_a = runner.invoke(
                app,
                ["implement", str(spec_a), "--project", str(tmp_path)],
            )
            assert result_a.exit_code == 0

        # --- Component B: calc_service ---
        spec_b = tmp_path / "specs" / "comp_b_spec.md"
        spec_b.write_text(
            "# comp_b\n\n## 1. Purpose\n\nComponent B does Y.\n",
            encoding="utf-8",
        )

        code_b = '"""Component B."""\n\ndef do_y() -> int:\n    return 42\n'
        tests_b = '"""Tests for comp_b."""\n\ndef test_do_y() -> None:\n    pass\n'

        llm_b = _make_sequenced_llm([code_b, tests_b])
        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None, llm_b, GenerationConfig(model="mock"),
            )
            result_b = runner.invoke(
                app,
                ["implement", str(spec_b), "--project", str(tmp_path)],
            )
            assert result_b.exit_code == 0

        # Verify files are independent
        code_a_path = tmp_path / "src" / "comp_a.py"
        code_b_path = tmp_path / "src" / "comp_b.py"
        test_a_path = tmp_path / "tests" / "test_comp_a.py"
        test_b_path = tmp_path / "tests" / "test_comp_b.py"

        assert code_a_path.exists() and code_b_path.exists()
        assert test_a_path.exists() and test_b_path.exists()

        # Content should not be mixed
        a_content = code_a_path.read_text(encoding="utf-8")
        b_content = code_b_path.read_text(encoding="utf-8")
        assert "do_x" in a_content and "do_y" not in a_content
        assert "do_y" in b_content and "do_x" not in b_content

    def test_check_code_with_rule_violations(self, tmp_path: Path) -> None:
        """Check on code that violates rules → exit code 1 with failures."""
        self._init_project(tmp_path)

        # Write code that violates rules:
        # - bare except (C06)
        # - TODO without ticket (C07)
        bad_code = (
            '"""Bad module."""\n'
            "\n"
            "# TODO: fix this later\n"
            "\n"
            "\n"
            "def broken():\n"
            "    try:\n"
            "        pass\n"
            "    except:\n"
            '        print("caught")\n'
        )

        bad_file = tmp_path / "src" / "bad_module.py"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text(bad_code, encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "check",
                str(bad_file),
                "--level", "code",
                "--project", str(tmp_path),
            ],
        )

        # Should report failures
        assert "FAIL" in result.output
        # Should show specific rule IDs that failed
        assert "C06" in result.output or "C07" in result.output


# ---------------------------------------------------------------------------
# Final Real-World Edge Cases
# ---------------------------------------------------------------------------


class TestRealWorldEdgeCases:
    """Edge cases modelled from realistic user workflows."""

    def _init_and_create_spec(self, tmp_path: Path) -> Path:
        """Helper: init project and write a realistic spec."""
        runner.invoke(app, ["init", "--project", str(tmp_path)])
        spec_path = tmp_path / "specs" / "greet_service_spec.md"
        spec_path.parent.mkdir(exist_ok=True)
        spec_path.write_text(
            "# greet_service\n\n"
            "## 1. Purpose\n\n"
            "Returns a personalized greeting for a given name.\n\n"
            "## 2. Contract\n\n"
            "```python\n"
            "def greet(name: str) -> str: ...\n"
            "```\n",
            encoding="utf-8",
        )
        return spec_path

    def test_implement_twice_overwrites_code(self, tmp_path: Path) -> None:
        """User runs implement twice → second run overwrites with new code."""
        spec_path = self._init_and_create_spec(tmp_path)

        code_v1 = (
            '"""Version 1."""\n\n'
            'def greet(name: str) -> str:\n'
            '    return f"Hi, {name}"\n'
        )
        tests_v1 = (
            '"""Tests v1."""\n\n'
            "def test_greet() -> None:\n"
            "    pass\n"
        )

        # First implement
        llm_v1 = _make_sequenced_llm([code_v1, tests_v1])
        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None, llm_v1, GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["implement", str(spec_path), "--project", str(tmp_path)],
            )
            assert result.exit_code == 0

        code_path = tmp_path / "src" / "greet_service.py"
        first_content = code_path.read_text(encoding="utf-8")
        assert "Version 1" in first_content

        # Second implement with different code (user iterated on spec)
        code_v2 = (
            '"""Version 2 — improved."""\n\n'
            'def greet(name: str) -> str:\n'
            '    return f"Hello, {name}!"\n'
        )
        tests_v2 = (
            '"""Tests v2."""\n\n'
            "def test_greet_v2() -> None:\n"
            "    pass\n"
        )

        llm_v2 = _make_sequenced_llm([code_v2, tests_v2])
        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None, llm_v2, GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["implement", str(spec_path), "--project", str(tmp_path)],
            )
            assert result.exit_code == 0

        # Code should now be v2, NOT v1
        updated_content = code_path.read_text(encoding="utf-8")
        assert "Version 2" in updated_content
        assert "Version 1" not in updated_content

        # Tests should also be v2
        test_path = tmp_path / "tests" / "test_greet_service.py"
        test_content = test_path.read_text(encoding="utf-8")
        assert "test_greet_v2" in test_content

    def test_llm_returns_markdown_fenced_code(self, tmp_path: Path) -> None:
        """LLM wraps code in ```python fences → fences are stripped E2E."""
        spec_path = self._init_and_create_spec(tmp_path)

        # Simulate what LLMs actually return: markdown-wrapped code
        fenced_code = (
            "```python\n"
            '"""Greet service."""\n'
            "\n"
            "\n"
            "def greet(name: str) -> str:\n"
            '    return f"Hello, {name}!"\n'
            "```"
        )
        fenced_tests = (
            "```python\n"
            '"""Tests."""\n'
            "\n"
            "\n"
            "def test_greet() -> None:\n"
            "    assert True\n"
            "```"
        )

        fenced_llm = _make_sequenced_llm([fenced_code, fenced_tests])
        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None, fenced_llm, GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["implement", str(spec_path), "--project", str(tmp_path)],
            )
            assert result.exit_code == 0

        code_path = tmp_path / "src" / "greet_service.py"
        code_content = code_path.read_text(encoding="utf-8")

        # The markdown fences should be STRIPPED — no ```python or ``` in file
        assert "```" not in code_content, "Markdown fences were not stripped"
        assert "def greet" in code_content, "Function definition missing"

        # Tests should also be clean
        test_path = tmp_path / "tests" / "test_greet_service.py"
        test_content = test_path.read_text(encoding="utf-8")
        assert "```" not in test_content, "Markdown fences in test file"

    def test_llm_error_during_review_shows_error_verdict(
        self,
        tmp_path: Path,
    ) -> None:
        """LLM crashes during review → ERROR verdict, not a traceback."""
        spec_path = self._init_and_create_spec(tmp_path)

        # LLM that raises an exception
        error_llm = AsyncMock()
        error_llm.available.return_value = True

        async def _crash(messages: object, config: object = None) -> None:
            from specweaver.llm.errors import GenerationError

            msg = "Service unavailable"
            raise GenerationError(msg)

        error_llm.generate = _crash

        with patch("specweaver.cli._require_llm_adapter") as mock_req:
            mock_req.return_value = (
                None, error_llm, GenerationConfig(model="mock"),
            )
            result = runner.invoke(
                app,
                ["review", str(spec_path), "--project", str(tmp_path)],
            )

        # Should NOT show a Python traceback
        assert "Traceback" not in result.output
        # Should show ERROR verdict (reviewer catches the exception)
        assert "ERROR" in result.output
        # Should contain the error message
        assert "Service unavailable" in result.output or "failed" in result.output.lower()


