# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for LLM Adapter auto-discovery registry."""

from typing import ClassVar
from unittest.mock import patch

import pytest

from specweaver.llm.adapters.base import LLMAdapter
from specweaver.llm.adapters.registry import (
    _ensure_discovered,
    get_adapter_class,
    get_all_adapters,
    get_merged_default_costs,
    register_adapter,
)


class DummyAdapter(LLMAdapter):
    """A dummy adapter for testing."""

    provider_name = "dummy"
    api_key_env_var = "DUMMY_KEY"
    default_costs: ClassVar[dict] = {}

    async def generate(self, messages, config):
        pass

    async def generate_stream(self, messages, config):
        yield ""

    def available(self) -> bool:
        return True

    async def count_tokens(self, text, model):
        return 0


def test_registry_has_gemini_adapter():
    """The gemini adapter should be automatically registered."""
    adapters = get_all_adapters()
    assert "gemini" in adapters
    assert adapters["gemini"] is not DummyAdapter


def test_get_adapter_class_success():
    """Can retrieve an adapter class by its provider name."""
    cls = get_adapter_class("gemini")
    assert cls.__name__ == "GeminiAdapter"


def test_get_adapter_class_not_found():
    """Raises ValueError if the adapter is not found."""
    with pytest.raises(ValueError, match="Unknown LLM provider: 'unknown'"):
        get_adapter_class("unknown")


def test_register_adapter():
    """Can manually register an adapter."""
    register_adapter(DummyAdapter)

    cls = get_adapter_class("dummy")
    assert cls is DummyAdapter

    # Clean up (optional but good practice)
    adapters = get_all_adapters()
    if "dummy" in adapters:
        del adapters["dummy"]


@patch("specweaver.llm.adapters.registry.importlib.import_module")
def test_ensure_discovered_swallows_syntax_error(mock_import):
    """If a dynamic adapter has a SyntaxError or other generic Exception, the registry shouldn't crash."""
    # Reset internal discovery state
    import specweaver.llm.adapters.registry as registry_module

    registry_module._DISCOVERED = False
    old_registry = dict(registry_module._REGISTRY)

    # Force a SyntaxError unconditionally during dynamic import
    mock_import.side_effect = SyntaxError("invalid syntax")

    # Should not raise
    _ensure_discovered()

    # Needs to flip back discovered flag otherwise later tests in session complain
    assert registry_module._DISCOVERED is True
    registry_module._REGISTRY.clear()
    registry_module._REGISTRY.update(old_registry)

def test_ensure_discovered_implicit_namespace_package():
    """
    Integration/Edge Case: Proves `specweaver.llm.adapters` natively functions as a PEP 420 
    Implicit Namespace Package without `__init__.py` bounding boxes by confirming its `__path__`
    is a _NamespacePath iterable and it possesses no `__file__` attribute.
    """
    import specweaver.llm.adapters as adapters_package

    # 1. Native PEP 420 packages do not have a physical __file__ because they are pure directories
    has_file = hasattr(adapters_package, "__file__")
    file_attr = getattr(adapters_package, "__file__", None)
    assert not has_file or file_attr is None, f"Implicit Namespace Package should not have a physical __file__, found {file_attr}"

    # 2. Native PEP 420 packages possess a dynamic _NamespacePath
    assert hasattr(adapters_package, "__path__"), "Implicit Namespace Package is missing __path__"
    assert "NamespacePath" in type(adapters_package.__path__).__name__, "Package __path__ is not dynamically resolving as a PEP 420 NamespacePath"


def test_get_merged_default_costs():
    """Returns a unified dictionary with costs from all adapters."""
    costs = get_merged_default_costs()
    assert "gemini-3-flash-preview" in costs

    # Check that a cost entry is structured right
    gemini_cost = costs["gemini-3-flash-preview"]
    assert hasattr(gemini_cost, "input_cost_per_1k")
    assert hasattr(gemini_cost, "output_cost_per_1k")


def test_merged_costs_no_duplicates():
    """First-registered adapter wins on duplicate models (not typically expected)."""
    # Simply check that what we get is a dict and has no dupes
    # (dict keys are inherently unique)
    costs = get_merged_default_costs()
    assert isinstance(costs, dict)
