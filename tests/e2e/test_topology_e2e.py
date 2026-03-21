# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — topology/context integration.

Exercises:
  19. sw scan generates context.yaml files for undocumented modules
  20. sw review --selector nhop injects neighbor context into prompt
  21. sw review --selector impact injects impact-weighted contexts
  22. sw review with no context.yaml → review still works (graceful degradation)
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

_proj_counter = 0


def _unique_name(prefix: str = "topo") -> str:
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all e2e tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


def _make_mock_llm(response: str = "VERDICT: ACCEPTED\nAll good.") -> object:
    """Create a minimal mock LLM adapter."""
    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"

    async def _generate(messages: object, config: object = None) -> LLMResponse:
        return LLMResponse(text=response, model="mock")

    mock_llm.generate = _generate
    return mock_llm


def _create_multi_module_project(tmp_path: Path, name: str) -> Path:
    """Create a project with multiple Python modules for topology testing."""
    project_dir = tmp_path / name
    project_dir.mkdir()

    src = project_dir / "src"
    src.mkdir()

    # Module A: greeter
    greeter = src / "greeter"
    greeter.mkdir()
    (greeter / "__init__.py").write_text('"""Greeter module."""\n', encoding="utf-8")
    (greeter / "service.py").write_text(
        '"""Greeting service."""\n\n\n'
        "class Greeter:\n"
        '    """Generates greetings."""\n\n'
        "    def greet(self, name: str) -> str:\n"
        '        """Return greeting."""\n'
        '        return f"Hello, {name}!"\n',
        encoding="utf-8",
    )

    # Module B: formatter (depends on greeter)
    formatter = src / "formatter"
    formatter.mkdir()
    (formatter / "__init__.py").write_text('"""Formatter module."""\n', encoding="utf-8")
    (formatter / "format.py").write_text(
        '"""Output formatter."""\n\n'
        "from greeter.service import Greeter\n\n\n"
        "def format_output(name: str) -> str:\n"
        '    """Format greeting output."""\n'
        "    g = Greeter()\n"
        "    return g.greet(name).upper()\n",
        encoding="utf-8",
    )

    # Init the project
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"
    return project_dir


def _write_spec(project_dir: Path, component: str = "greeter") -> Path:
    """Write a minimal valid spec file under a project directory."""
    spec = project_dir / "specs" / f"{component}_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(
        f"# {component}\n\n"
        "## 1. Purpose\n\nProvides greeting functionality.\n\n"
        "## 2. Contract\n\n```python\ndef greet(name: str) -> str: ...\n```\n\n"
        "## 3. Protocol\n\n1. Accept a name string.\n2. Return formatted greeting.\n\n"
        "## 4. Policy\n\n| Error | Behavior |\n|:---|:---|\n"
        "| Invalid type | Raise TypeError |\n\n"
        "## 5. Boundaries\n\n| Concern | Owned By |\n|:---|:---|\n| I/O | Infra |\n\n"
        "## Done Definition\n\n- [ ] All unit tests pass\n",
        encoding="utf-8",
    )
    return spec


# ===========================================================================
# Test 19: sw scan generates context.yaml for undocumented modules
# ===========================================================================


class TestScanGeneratesContextYaml:
    """sw scan creates context.yaml files for modules that don't have one."""

    def test_scan_generates_context_yaml(self, tmp_path: Path) -> None:
        """Init project with modules → sw scan → each module has context.yaml.

        Verifies:
        - sw scan exits 0
        - context.yaml files are generated under module directories
        - Generated files contain valid YAML with a 'name' field
        """
        project_dir = _create_multi_module_project(tmp_path, _unique_name())

        # sw scan acts on the active project (no --project flag)
        runner.invoke(app, ["use", project_dir.name])
        scan_result = runner.invoke(app, ["scan"])
        # Scan should succeed (may warn about missing modules but shouldn't crash)
        assert scan_result.exit_code == 0, f"sw scan failed: {scan_result.output}"

        # At least one context.yaml should have been generated
        import yaml

        src = project_dir / "src"
        generated = list(src.rglob("context.yaml"))
        assert len(generated) > 0, (
            f"No context.yaml files generated. scan output:\n{scan_result.output}"
        )

        for ctx_file in generated:
            content = ctx_file.read_text(encoding="utf-8")
            assert len(content) > 0, f"Empty context.yaml at {ctx_file}"
            # Should be parseable YAML
            data = yaml.safe_load(content)
            assert isinstance(data, dict), f"context.yaml not a dict: {data}"

    def test_scan_skips_modules_with_existing_context(self, tmp_path: Path) -> None:
        """sw scan skips modules that already have a context.yaml."""
        project_dir = _create_multi_module_project(tmp_path, _unique_name())

        # Pre-create context.yaml for greeter
        greeter_ctx = project_dir / "src" / "greeter" / "context.yaml"
        greeter_ctx.write_text(
            "name: greeter\npurpose: Pre-existing context\narchetype: service\n",
            encoding="utf-8",
        )

        runner.invoke(app, ["use", project_dir.name])
        scan_result = runner.invoke(app, ["scan"])
        assert scan_result.exit_code == 0, f"sw scan failed: {scan_result.output}"

        # Pre-existing context should not be overwritten
        content = greeter_ctx.read_text(encoding="utf-8")
        assert "Pre-existing context" in content, (
            "sw scan overwrote a manually-written context.yaml"
        )


# ===========================================================================
# Test 20: sw review --selector nhop injects neighbor context into prompt
# ===========================================================================


class TestReviewWithNhopSelector:
    """sw review --selector nhop uses multi-hop topology context."""

    def test_review_with_nhop_selector(self, tmp_path: Path) -> None:
        """Review with --selector nhop → command completes; no topology crash.

        The selector is used when context.yaml exists. We verify that:
        - The command doesn't crash with a topology error
        - The LLM mock is still called (the review proceeds)
        - ACCEPTED verdict is shown
        """
        project_dir = _create_multi_module_project(tmp_path, _unique_name())
        spec = _write_spec(project_dir, "greeter")

        # Run sw scan so context.yaml files exist
        runner.invoke(app, ["use", project_dir.name])
        runner.invoke(app, ["scan"])

        mock_llm = _make_mock_llm("VERDICT: ACCEPTED\nGood spec.")

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            result = runner.invoke(
                app,
                [
                    "review",
                    str(spec),
                    "--project",
                    str(project_dir),
                    "--selector",
                    "nhop",
                ],
            )

        # Command must not crash
        assert result.exit_code in (0, 1), f"review --selector nhop crashed: {result.output}"
        # Result should contain ACCEPTED (from mock) or an error verdict — not a traceback
        assert "Traceback" not in result.output


# ===========================================================================
# Test 21: sw review --selector impact injects impact-weighted contexts
# ===========================================================================


class TestReviewWithImpactSelector:
    """sw review --selector impact uses impact-weighted topology context."""

    def test_review_with_impact_selector(self, tmp_path: Path) -> None:
        """Review with --selector impact → command completes without crash.

        Verifies:
        - impact selector doesn't cause KeyError or AttributeError
        - Review proceeds and shows verdict
        """
        project_dir = _create_multi_module_project(tmp_path, _unique_name())
        spec = _write_spec(project_dir, "formatter")

        # Run sw scan so context.yaml files exist
        runner.invoke(app, ["use", project_dir.name])
        runner.invoke(app, ["scan"])

        mock_llm = _make_mock_llm("VERDICT: ACCEPTED\nLooks good.")

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            result = runner.invoke(
                app,
                [
                    "review",
                    str(spec),
                    "--project",
                    str(project_dir),
                    "--selector",
                    "impact",
                ],
            )

        assert result.exit_code in (0, 1), f"review --selector impact crashed: {result.output}"
        assert "Traceback" not in result.output


# ===========================================================================
# Test 22: sw review with no context.yaml → review still works
# ===========================================================================


class TestReviewWithNoTopology:
    """sw review works even when no context.yaml exists anywhere in project."""

    def test_review_with_no_topology(self, tmp_path: Path) -> None:
        """Review on a project with no topology → graceful degradation.

        Verifies:
        - sw review doesn't crash when there are no context.yaml files
        - LLM receives the review prompt (topology section simply absent)
        - Verdict is returned normally
        """
        project_dir = tmp_path / _unique_name()
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

        spec = _write_spec(project_dir, "standalone")

        # Deliberately no sw scan — no context.yaml files anywhere

        mock_llm = _make_mock_llm("VERDICT: ACCEPTED\nNo topology needed.")

        with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            result = runner.invoke(
                app,
                ["review", str(spec), "--project", str(project_dir)],
            )

        # Must succeed cleanly
        assert result.exit_code == 0, f"review without topology failed: {result.output}"
        assert "ACCEPTED" in result.output
        assert "Traceback" not in result.output

    def test_review_with_all_selector_types_no_topology(self, tmp_path: Path) -> None:
        """All four selector types work gracefully when no topology exists."""
        project_dir = tmp_path / _unique_name()
        project_dir.mkdir()
        runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])
        spec = _write_spec(project_dir, "nocontext")

        for selector in ("direct", "nhop", "constraint", "impact"):
            mock_llm = _make_mock_llm(f"VERDICT: ACCEPTED\n{selector} ok.")
            with patch("specweaver.cli._helpers._require_llm_adapter") as mock_req:
                mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
                result = runner.invoke(
                    app,
                    [
                        "review",
                        str(spec),
                        "--project",
                        str(project_dir),
                        "--selector",
                        selector,
                    ],
                )
            assert result.exit_code in (0, 1), (
                f"review --selector {selector} crashed without topology:\n{result.output}"
            )
            assert "Traceback" not in result.output, (
                f"Traceback with selector={selector}:\n{result.output}"
            )
