# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM adapter interface and concrete implementations."""

import contextlib
import importlib
import logging
import pkgutil
from pathlib import Path

logger = logging.getLogger(__name__)

from specweaver.llm.adapters.base import LLMAdapter

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

    # Register all subclasses that were loaded
    for cls in LLMAdapter.__subclasses__():
        if cls.__name__ != "DummyAdapter": # skip test dummies if any leaked
            register_adapter(cls)  # type: ignore

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

__all__ = ["get_adapter_class", "get_all_adapters", "register_adapter"]
