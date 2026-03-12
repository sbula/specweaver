# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for ContextInferrer — auto-generation of missing context.yaml."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specweaver.context.inferrer import ContextInferrer, InferenceResult


@pytest.fixture()
def python_module(tmp_path: Path) -> Path:
    """A Python module with importable code but NO context.yaml."""
    pkg = tmp_path / "price_feed"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Price feed adapter for Binance WebSocket."""\n'
    )
    (pkg / "client.py").write_text(
        'import requests\n'
        '\n'
        'class PriceFeedClient:\n'
        '    """Connects to Binance and streams price data."""\n'
        '    pass\n'
    )
    return pkg


@pytest.fixture()
def python_module_with_context(tmp_path: Path) -> Path:
    """A Python module that ALREADY has a context.yaml."""
    pkg = tmp_path / "existing"
    pkg.mkdir()
    (pkg / "__init__.py").write_text('"""Existing module."""\n')
    (pkg / "context.yaml").write_text(
        'name: existing\nlevel: module\npurpose: Already defined.\narchetype: pure-logic\n'
    )
    return pkg


@pytest.fixture()
def empty_module(tmp_path: Path) -> Path:
    """An empty directory — no source files at all."""
    d = tmp_path / "empty"
    d.mkdir()
    return d


@pytest.fixture()
def inferrer() -> ContextInferrer:
    return ContextInferrer()


# ---------------------------------------------------------------------------
# Core behavior tests
# ---------------------------------------------------------------------------


class TestInference:
    """Test context.yaml auto-generation."""

    def test_generates_context_yaml(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module)
        assert result.was_generated is True
        assert (python_module / "context.yaml").is_file()

    def test_generated_has_auto_header(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        inferrer.infer_and_write(python_module)
        content = (python_module / "context.yaml").read_text(encoding="utf-8")
        assert "AUTO-GENERATED" in content

    def test_generated_fields(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module)
        assert result.node.name == "price_feed"
        assert result.node.purpose == "Price feed adapter for Binance WebSocket."
        assert result.node.archetype == "adapter"  # imports 'requests'
        assert "requests" in result.node.imports

    def test_generated_yaml_is_parseable(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        inferrer.infer_and_write(python_module)
        yaml = YAML()
        data = yaml.load(python_module / "context.yaml")
        assert data["name"] == "price_feed"
        assert "purpose" in data

    def test_infers_level_from_parent(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module, parent_level="service")
        assert result.node.level == "module"

    def test_default_level_is_module(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module)
        assert result.node.level == "module"


class TestSkipBehavior:
    """Test cases where inference is skipped."""

    def test_skips_existing_context(
        self, inferrer: ContextInferrer, python_module_with_context: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module_with_context)
        assert result.was_generated is False

    def test_skips_empty_dir(
        self, inferrer: ContextInferrer, empty_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(empty_module)
        assert result.was_generated is False
        assert not (empty_module / "context.yaml").is_file()


class TestWarnings:
    """Test that appropriate warnings are generated."""

    def test_warning_when_generated(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module)
        assert len(result.warnings) > 0
        assert any("price_feed" in w for w in result.warnings)

    def test_no_warning_when_skipped(
        self, inferrer: ContextInferrer, python_module_with_context: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module_with_context)
        assert len(result.warnings) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestInferrerEdgeCases:
    """Edge cases for auto-inference."""

    def test_idempotent_second_run_skips(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        """Running twice on the same dir: first generates, second skips."""
        result1 = inferrer.infer_and_write(python_module)
        assert result1.was_generated is True

        result2 = inferrer.infer_and_write(python_module)
        assert result2.was_generated is False  # context.yaml now exists

    def test_pycache_only_skipped(self, inferrer: ContextInferrer, tmp_path: Path) -> None:
        """__pycache__ dirs should not get context.yaml."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-313.pyc").write_bytes(b"")
        result = inferrer.infer_and_write(cache)
        assert result.was_generated is False

    def test_level_from_system_parent(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module, parent_level="system")
        assert result.node.level == "service"

    def test_level_from_module_parent(
        self, inferrer: ContextInferrer, python_module: Path,
    ) -> None:
        result = inferrer.infer_and_write(python_module, parent_level="module")
        assert result.node.level == "sub-module"

    def test_no_docstring_purpose_is_todo(
        self, inferrer: ContextInferrer, tmp_path: Path,
    ) -> None:
        """Module with no docstring gets a TODO purpose."""
        pkg = tmp_path / "no_doc"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("")
        (pkg / "code.py").write_text("x = 1\n")
        result = inferrer.infer_and_write(pkg)
        assert result.was_generated is True
        assert "TODO" in result.node.purpose

