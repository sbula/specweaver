# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The shipped catalogue loads, and the machine settings file corrects it.

Proves: C-FLOW-13 FR-6, NFR-1

| Bucket | Case |
|---|---|
| Happy | the shipped files load and price a current hosted model |
| Boundary | loading both files stays under the 50 ms budget |
| Degradation | a machine-file correction reaches the facts through the settings reader |
| Hostile | the GB10's model is not priced from a hosted namesake |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.infrastructure.llm.catalogue import CATALOGUE_DIR, Catalogue, shipped_catalogue

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_the_shipped_catalogue_prices_a_hosted_model() -> None:
    facts = shipped_catalogue().facts("anthropic", "claude-sonnet-4-5", {})

    assert facts is not None
    assert facts.usd_per_million_input and facts.usd_per_million_input > 0
    assert facts.thinking_in_output_cap is True
    assert shipped_catalogue().source["repo_commit"]


def test_loading_stays_within_the_budget() -> None:
    generated = (CATALOGUE_DIR / "models_dev.json").read_text(encoding="utf-8")
    local = (CATALOGUE_DIR / "local.toml").read_text(encoding="utf-8")

    start = time.perf_counter()
    Catalogue.from_texts(generated, local)

    assert time.perf_counter() - start < 0.05


def test_a_machine_correction_reaches_the_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.toml").write_text(
        '[models."claude-sonnet-4-5"]\nusd_per_million_input = 1.5\n', encoding="utf-8"
    )
    files = load_llm_settings(None)

    facts = shipped_catalogue().facts("anthropic", "claude-sonnet-4-5", files.machine.models)

    assert facts is not None
    assert facts.usd_per_million_input == 1.5
    assert facts.context and facts.context > 0


def test_the_local_model_is_not_priced_from_a_hosted_namesake() -> None:
    facts = shipped_catalogue().facts("openai-compatible", "qwen3-coder-next", {})

    assert facts is not None
    assert facts.context == 262144
    assert facts.usd_per_million_input is None
