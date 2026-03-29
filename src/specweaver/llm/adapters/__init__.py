# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM adapter interface and concrete implementations."""

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.llm.adapters.base import LLMAdapter

if TYPE_CHECKING:
    from specweaver.llm.telemetry import CostEntry

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[LLMAdapter]] = {}
_DISCOVERED = False


def register_adapter(adapter_cls: type[LLMAdapter]) -> None:
    """Register an adapter class by its provider_name."""
    if adapter_cls.provider_name:
        _REGISTRY[adapter_cls.provider_name] = adapter_cls


def _ensure_discovered() -> None:
    global _DISCOVERED
    if _DISCOVERED:
        return

    # Dynamically import all sibling modules to trigger class evaluation
    package_dir = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
        if module_name != "base":
            try:
                importlib.import_module(f".{module_name}", package=__name__)
            except Exception as e:
                logger.debug("Failed to load adapter module '%s': %s", module_name, e)

    # Recursively find all subclasses
    def _get_all_subclasses(cls: type[LLMAdapter]) -> list[type[LLMAdapter]]:
        return cls.__subclasses__() + [
            g for s in cls.__subclasses__() for g in _get_all_subclasses(s)
        ]

    # Register all subclasses that were loaded
    for cls in set(_get_all_subclasses(LLMAdapter)):  # type: ignore[type-abstract]
        if cls.__name__ != "DummyAdapter" and getattr(cls, "provider_name", None):
            register_adapter(cls)

    _DISCOVERED = True


def get_all_adapters() -> dict[str, type[LLMAdapter]]:
    """Get all registered adapter classes."""
    _ensure_discovered()
    return dict(_REGISTRY)


def get_adapter_class(provider_name: str) -> type[LLMAdapter]:
    """Get the adapter class for a given provider name.

    Raises:
        ValueError: If provider is unknown.
    """
    _ensure_discovered()
    if provider_name not in _REGISTRY:
        raise ValueError(f"Unknown LLM provider: {provider_name!r}")
    return _REGISTRY[provider_name]


def get_merged_default_costs() -> dict[str, "CostEntry"]:
    """Merge default costs from all registered adapters.

    Returns a unified dictionary mapping model names to their CostEntry.
    """
    _ensure_discovered()
    merged = {}
    for cls in _REGISTRY.values():
        if cls.default_costs:
            for model, cost in cls.default_costs.items():
                if model not in merged:
                    merged[model] = cost
    return merged


__all__ = ["get_adapter_class", "get_all_adapters", "get_merged_default_costs", "register_adapter"]
