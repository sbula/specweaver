# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import sys
from typing import Any

import pytest

from specweaver.sandbox.base import BaseTool
from specweaver.sandbox.registry import ToolRegistry, get_standard_registry


class TestBaseTool:
    def test_basetool_abc_instantiation_raises(self) -> None:
        with pytest.raises(TypeError):
            BaseTool()  # type: ignore

    def test_incomplete_tool_subclass_raises(self) -> None:
        class IncompleteTool(BaseTool):
            @property
            def role(self) -> str:
                return "test"
            # Missing definitions()

        with pytest.raises(TypeError):
            IncompleteTool()  # type: ignore

    def test_conforming_tool_instantiation(self) -> None:
        class ConformingTool(BaseTool):
            @property
            def role(self) -> str:
                return "test"

            def definitions(self) -> list[Any]:
                return [{"name": "test_tool"}]

        tool = ConformingTool()
        assert tool.role == "test"
        assert len(tool.definitions()) == 1

    def test_tool_boundary_empty_values(self) -> None:
        class EmptyTool(BaseTool):
            @property
            def role(self) -> str:
                return ""

            def definitions(self) -> list[Any]:
                return []

        tool = EmptyTool()
        assert tool.role == ""
        assert tool.definitions() == []


class TestToolRegistry:
    def test_registry_happy_path(self) -> None:
        registry = ToolRegistry()

        class DummyTool(BaseTool):
            @property
            def role(self) -> str: return "dummy"
            def definitions(self) -> list[Any]: return []

        registry.register("dummy", lambda **kwargs: DummyTool())

        tools = registry.create_tools(["dummy"])
        assert len(tools) == 1
        assert isinstance(tools[0], DummyTool)

    def test_registry_missing_factory_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        registry = ToolRegistry()
        tools = registry.create_tools(["missing_tool"])

        assert len(tools) == 0
        assert "Tool 'missing_tool' requested but not registered" in caplog.text

    def test_registry_factory_exception_handling(self, caplog: pytest.LogCaptureFixture) -> None:
        registry = ToolRegistry()

        class DummyTool(BaseTool):
            @property
            def role(self) -> str: return "dummy"
            def definitions(self) -> list[Any]: return []

        def crash_factory(**kwargs: Any) -> BaseTool:
            raise ValueError("Factory crash!")

        registry.register("crash", crash_factory)
        registry.register("dummy", lambda **kwargs: DummyTool())

        tools = registry.create_tools(["crash", "dummy"])

        assert len(tools) == 1
        assert isinstance(tools[0], DummyTool)
        assert "Failed to create tool 'crash'" in caplog.text
        assert "Factory crash!" in caplog.text

    def test_registry_lazy_resolution_preserves_namespace(self) -> None:

        # Remove the modules if they happen to be loaded already
        target_modules = [
            "specweaver.sandbox.filesystem.interfaces.facades",
            "specweaver.sandbox.code_structure.interfaces.tool",
            "specweaver.sandbox.web.interfaces.tool",
            "specweaver.sandbox.mcp.interfaces.tool",
            "specweaver.sandbox.mcp.interfaces.facades",
            "specweaver.sandbox.git.interfaces.facades",
            "specweaver.sandbox.protocol.interfaces.tool",
        ]

        for mod in target_modules:
            sys.modules.pop(mod, None)

        # Call get_standard_registry to set up closures
        _ = get_standard_registry()

        # Ensure that none of the heavy domains were imported just by calling get_standard_registry
        for mod in target_modules:
            assert mod not in sys.modules, f"Module {mod} was imported prematurely!"

        # Restore sys.modules just in case
        for mod in target_modules:
            sys.modules.pop(mod, None)

    def test_registry_duplicate_registration_overwrites(self) -> None:
        """Registering the same key twice silently overwrites the factory."""
        registry = ToolRegistry()

        class ToolA(BaseTool):
            @property
            def role(self) -> str: return "a"
            def definitions(self) -> list[Any]: return []

        class ToolB(BaseTool):
            @property
            def role(self) -> str: return "b"
            def definitions(self) -> list[Any]: return []

        registry.register("x", lambda **kwargs: ToolA())
        registry.register("x", lambda **kwargs: ToolB())

        tools = registry.create_tools(["x"])
        assert len(tools) == 1
        assert isinstance(tools[0], ToolB)
        assert tools[0].role == "b"

    @pytest.mark.xfail(reason="Intentionally RED at end of SF-1. Domains don't implement BaseTool yet.")
    def test_standard_registry_tools_are_basetool_instances(self) -> None:
        """TDD red-phase marker for SF-2: domain facades must inherit BaseTool."""
        registry = get_standard_registry()
        # Will crash or return non-BaseTool instances until SF-2 makes
        # domain facades conform to BaseTool.
        tools = registry.create_tools(["web"], role="reviewer")
        assert len(tools) == 1
        assert isinstance(tools[0], BaseTool), "Domain tools must inherit from BaseTool"
