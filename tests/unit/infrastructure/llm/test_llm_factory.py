# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`llm/factory.py` builds nothing any more; it only keeps the `LLMAdapterError` name resolving."""

from __future__ import annotations


def test_the_factory_re_exports_the_one_adapter_error() -> None:
    """One class, not a copy: `except factory.LLMAdapterError` must catch what adapters raise."""
    from specweaver.infrastructure.llm import errors, factory

    assert factory.LLMAdapterError is errors.LLMAdapterError
