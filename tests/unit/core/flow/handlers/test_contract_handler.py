# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for GenerateContractHandler — Feature 3.28 SF-A."""

from __future__ import annotations

import typing
from unittest.mock import MagicMock

from specweaver.core.flow.handlers.generation import GenerateContractHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if typing.TYPE_CHECKING:
    from pathlib import Path

from specweaver.core.flow.engine.models import (
    VALID_STEP_COMBINATIONS,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.state import StepStatus


class TestContractEnumAndCombinations:
    def test_contract_target_exists(self) -> None:
        assert hasattr(StepTarget, "CONTRACT")
        assert StepTarget.CONTRACT.value == "contract"

    def test_valid_step_combination(self) -> None:
        assert (StepAction.GENERATE, StepTarget.CONTRACT) in VALID_STEP_COMBINATIONS


# ── Static method tests ──────────────────────────────────────────────────

_SAMPLE_CONTRACT_SECTION = """\
## 2. Contract

### Interface

```python
def greet(name: str) -> str:
    \"\"\"Return a greeting for the given name.\"\"\"

def farewell(name: str) -> str:
    \"\"\"Say goodbye.\"\"\"
```
"""

_SAMPLE_SPEC = (
    """\
## 1. Purpose

A greeter.

"""
    + _SAMPLE_CONTRACT_SECTION
)


class TestContractHandlerStaticMethods:
    def test_extract_contract(self) -> None:
        handler = GenerateContractHandler()
        result = handler._extract_contract(_SAMPLE_SPEC)
        assert result is not None
        assert "greet" in result

    def test_extract_signatures(self) -> None:
        handler = GenerateContractHandler()
        contract = handler._extract_contract(_SAMPLE_SPEC)
        assert contract is not None
        sigs = handler._extract_signatures(contract)
        assert len(sigs) == 2
        assert any("greet" in s for s in sigs)
        assert any("farewell" in s for s in sigs)

    def test_extract_docstrings(self) -> None:
        handler = GenerateContractHandler()
        contract = handler._extract_contract(_SAMPLE_SPEC)
        assert contract is not None
        docstrings = handler._extract_docstrings(contract)
        assert "greet" in docstrings
        assert "greeting" in docstrings["greet"].lower()

    def test_render_protocol_with_docstrings(self) -> None:
        handler = GenerateContractHandler()
        sigs = ["def greet(name: str) -> str", "def farewell(name: str) -> str"]
        docstrings = {"greet": "Return a greeting.", "farewell": "Say goodbye."}
        output = handler._render_protocol("Greeter", sigs, docstrings)
        assert "class GreeterProtocol(Protocol):" in output
        assert "def greet" in output
        assert "def farewell" in output
        assert '"""Return a greeting."""' in output
        assert '"""Say goodbye."""' in output

    def test_render_protocol_without_docstrings(self) -> None:
        handler = GenerateContractHandler()
        sigs = ["def greet(name: str) -> str"]
        output = handler._render_protocol("Greeter", sigs)
        assert "class GreeterProtocol(Protocol):" in output
        assert "        ..." in output


# ── execute() integration tests ──────────────────────────────────────────


def _make_context(tmp_path: Path, spec_content: str) -> MagicMock:
    """Create a minimal mock RunContext for testing."""
    spec_file = tmp_path / "greeter_spec.md"
    spec_file.write_text(spec_content, encoding="utf-8")
    ctx = MagicMock()
    ctx.spec_path = spec_file
    ctx.project_path = tmp_path
    ctx.api_contract_paths = None
    return ctx


class TestContractHandlerExecute:
    async def test_execute_creates_contract_file(self, tmp_path: Path) -> None:
        ctx = _make_context(tmp_path, _SAMPLE_SPEC)
        handler = GenerateContractHandler()
        result = await handler.execute(MagicMock(), ctx)
        assert result.status == StepStatus.PASSED
        contract_file = tmp_path / "contracts" / "greeter_contract.py"
        assert contract_file.exists()
        content = contract_file.read_text(encoding="utf-8")
        assert "class GreeterProtocol(Protocol):" in content

    async def test_execute_wires_api_contract_paths(self, tmp_path: Path) -> None:
        ctx = _make_context(tmp_path, _SAMPLE_SPEC)
        handler = GenerateContractHandler()
        await handler.execute(MagicMock(), ctx)
        assert ctx.api_contract_paths is not None
        assert len(ctx.api_contract_paths) == 1
        assert "greeter_contract.py" in ctx.api_contract_paths[0]

    async def test_execute_no_contract_section_errors(self, tmp_path: Path) -> None:
        ctx = _make_context(tmp_path, "## 1. Purpose\n\nNo contract here.\n")
        handler = GenerateContractHandler()
        result = await handler.execute(MagicMock(), ctx)
        assert result.status == StepStatus.ERROR

    async def test_execute_no_signatures_errors(self, tmp_path: Path) -> None:
        spec = "## 2. Contract\n\nJust text, no code blocks.\n"
        ctx = _make_context(tmp_path, spec)
        handler = GenerateContractHandler()
        result = await handler.execute(MagicMock(), ctx)
        assert result.status == StepStatus.ERROR


# ── Registration test ────────────────────────────────────────────────────


class TestContractHandlerRegistration:
    def test_handler_registered_in_registry(self) -> None:


        registry = StepHandlerRegistry()
        handler = registry.get(StepAction.GENERATE, StepTarget.CONTRACT)
        assert handler is not None
        assert isinstance(handler, GenerateContractHandler)


# ── T8: Language dispatch (SF-B2) ───────────────────────────────────────────


class TestContractHandlerLanguageDispatch:
    """GenerateContractHandler must use render_contract() dispatch — not hardcode Python."""

    async def test_java_project_generates_java_interface(self, tmp_path: Path) -> None:
        """Java project (pom.xml) → interface in contracts/greeter_contract.java."""
        (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        ctx = _make_context(tmp_path, _SAMPLE_SPEC)
        handler = GenerateContractHandler()
        result = await handler.execute(MagicMock(), ctx)
        assert result.status == StepStatus.PASSED
        contract_file = tmp_path / "contracts" / "greeter_contract.java"
        assert contract_file.exists(), f"Expected {contract_file}"
        content = contract_file.read_text(encoding="utf-8")
        assert "interface GreeterContract" in content
        assert "package contracts;" in content

    async def test_kotlin_project_generates_kotlin_interface(self, tmp_path: Path) -> None:
        """Kotlin project (build.gradle) → interface in contracts/greeter_contract.kt."""
        (tmp_path / "build.gradle").write_text("plugins {}", encoding="utf-8")
        ctx = _make_context(tmp_path, _SAMPLE_SPEC)
        handler = GenerateContractHandler()
        result = await handler.execute(MagicMock(), ctx)
        assert result.status == StepStatus.PASSED
        contract_file = tmp_path / "contracts" / "greeter_contract.kt"
        assert contract_file.exists(), f"Expected {contract_file}"
        content = contract_file.read_text(encoding="utf-8")
        assert "interface GreeterContract" in content

    async def test_python_project_generates_python_protocol(self, tmp_path: Path) -> None:
        """Python project (default) → Protocol in contracts/greeter_contract.py."""
        ctx = _make_context(tmp_path, _SAMPLE_SPEC)
        handler = GenerateContractHandler()
        result = await handler.execute(MagicMock(), ctx)
        assert result.status == StepStatus.PASSED
        contract_file = tmp_path / "contracts" / "greeter_contract.py"
        assert contract_file.exists()
        content = contract_file.read_text(encoding="utf-8")
        assert "class GreeterProtocol(Protocol):" in content
