# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The shipped catalogue loads, and the machine settings file corrects it.

Proves: C-FLOW-13 FR-6, FR-18, NFR-1

| Bucket | Case |
|---|---|
| Happy | the shipped list loads; every hosted model on it has both prices and an output limit |
| Boundary | loading it stays under the 50 ms budget |
| Degradation | a machine-file correction reaches the facts through the settings reader |
| Hostile | the GB10's model is not priced from a hosted namesake |
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.infrastructure.llm.catalogue import CATALOGUE_FILE, Catalogue, shipped_catalogue

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_every_hosted_model_on_the_shipped_list_is_priced() -> None:
    catalogue = shipped_catalogue()
    hosted = [key for key in catalogue.models if not key.startswith("openai-compatible/")]

    assert hosted
    for key in hosted:
        kind, model = key.split("/", 1)
        facts = catalogue.facts(kind, model, {})
        assert facts is not None and facts.max_output, key
        assert facts.usd_per_million_input and facts.usd_per_million_output, key
    assert catalogue.checked


def test_loading_stays_within_the_budget() -> None:
    text = CATALOGUE_FILE.read_text(encoding="utf-8")

    start = time.perf_counter()
    Catalogue.from_text(text)

    assert time.perf_counter() - start < 0.05


def test_a_machine_correction_reaches_the_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
    (tmp_path / "settings.toml").write_text(
        '[models."claude-sonnet-5"]\nusd_per_million_input = 1.5\n', encoding="utf-8"
    )
    files = load_llm_settings(None)

    facts = shipped_catalogue().facts("anthropic", "claude-sonnet-5", files.machine.models)

    assert facts is not None
    assert facts.usd_per_million_input == 1.5
    assert facts.context and facts.context > 0


def test_the_local_model_is_not_priced_from_a_hosted_namesake() -> None:
    facts = shipped_catalogue().facts("openai-compatible", "qwen3-coder-next", {})

    assert facts is not None
    assert facts.context == 262144
    assert facts.usd_per_million_input is None
    assert facts.sampling is not None
    assert (facts.sampling.temperature, facts.sampling.top_p, facts.sampling.top_k) == (
        1.0,
        0.95,
        40,
    )


def test_a_20_kb_settings_file_resolves_within_the_budget() -> None:
    """NFR-1: read, validate and layer the settings once, under 50 ms for a file under 20 KB."""
    from specweaver.core.config.llm_settings import LlmSettingsFiles, resolve_roles

    models = "".join(
        f'[models."m{i}"]\nusd_per_million_input = 1.0\nusd_per_million_output = 2.0\n'
        f"max_output = 4000\n\n"
        for i in range(210)
    )
    machine = (
        '[servers.gb10]\nkind = "openai-compatible"\nbase_url = "http://gb10:8000/v1"\n'
        'private = true\nmax_parallel = 4\n\n[roles]\ndefault = "m1@gb10"\nreview = "m2@gb10"\n\n'
        "[brake]\nhosted_spend_per_run = 1\ntokens_per_run = 1000\nagent_turns = 5\n\n" + models
    )
    assert 15_000 < len(machine.encode()) < 20_480

    start = time.perf_counter()
    files = LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="settings.toml", project_text="", project_source="-"
    )
    resolve_roles(files)

    assert time.perf_counter() - start < 0.05
