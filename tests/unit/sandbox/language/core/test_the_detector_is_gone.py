# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The project-language detector is gone, with no shim; the run's profile decides.

Proves: TECH-079 NFR-3, TECH-079 FR-7

| Bucket | Case |
|---|---|
| Happy | not applicable — the claim is an absence |
| Boundary | the module and both names are gone; the factory module no longer re-exports one |
| Degradation | not applicable — nothing runs |
| Hostile | an import of the old names fails loudly, never resolves to a stand-in |
"""

from __future__ import annotations

import importlib

import pytest


def test_the_detector_module_is_gone() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("specweaver.sandbox.language.core.detect")


@pytest.mark.parametrize("name", ["detect_language", "detect_scenario_extension"])
def test_the_converter_factory_reexports_no_detector(name: str) -> None:
    module = importlib.import_module("specweaver.sandbox.language.core.scenario_converter_factory")

    assert not hasattr(module, name)
