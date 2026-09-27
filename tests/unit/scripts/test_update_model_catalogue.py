# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The catalogue is regenerated from models.dev as a reviewable file, never fetched at runtime.

Proves: C-FLOW-13 FR-18

| Bucket | Case |
|---|---|
| Happy | the five hosted providers are kept under our kind names, prices per 1M tokens |
| Boundary | a model without a price keeps no price rather than 0; output is sorted, so a rerun diffs clean |
| Degradation | a model without limits, or with a zero limit, still converts; the limit is unknown |
| Hostile | deprecated models and other providers are dropped |
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]

_API = {
    "google": {
        "models": {
            "gemini-2.5-pro": {
                "cost": {"input": 1.25, "output": 10},
                "limit": {"context": 1048576, "output": 65536},
                "tool_call": True,
            },
            "gemini-1.0-pro": {"status": "deprecated", "cost": {"input": 1, "output": 2}},
        }
    },
    "anthropic": {"models": {"claude-free": {"tool_call": False, "limit": {"context": 1000}}}},
    "alibaba-cn": {"models": {"qwen-plus": {"tool_call": True}}},
    "groq": {"models": {"llama": {"cost": {"input": 0.1, "output": 0.1}}}},
}
_STAMP = {"fetched": "2026-09-27", "etag": '"abc"', "repo_commit": "0620137a", "license": "MIT"}


def _load() -> ModuleType:
    path = REPO_ROOT / "scripts" / "update_model_catalogue.py"
    spec = importlib.util.spec_from_file_location("update_model_catalogue", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["update_model_catalogue"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod() -> ModuleType:
    return _load()


def test_the_hosted_providers_are_kept_under_our_kind_names(mod: ModuleType) -> None:
    models = mod.convert(_API, _STAMP)["models"]

    assert models["gemini/gemini-2.5-pro"] == {
        "context": 1048576,
        "max_output": 65536,
        "tool_calls": True,
        "usd_per_million_input": 1.25,
        "usd_per_million_output": 10,
    }
    assert "qwen/qwen-plus" in models


def test_a_model_without_a_price_has_no_price(mod: ModuleType) -> None:
    free = mod.convert(_API, _STAMP)["models"]["anthropic/claude-free"]

    assert "usd_per_million_input" not in free
    assert free == {"context": 1000, "tool_calls": False}


def test_a_model_without_limits_still_converts(mod: ModuleType) -> None:
    assert mod.convert(_API, _STAMP)["models"]["qwen/qwen-plus"] == {"tool_calls": True}


def test_deprecated_models_and_other_providers_are_dropped(mod: ModuleType) -> None:
    models = mod.convert(_API, _STAMP)["models"]

    assert "gemini/gemini-1.0-pro" not in models
    assert not any(key.startswith("groq/") for key in models)


def test_the_file_is_stamped_and_sorted(mod: ModuleType) -> None:
    text = mod.render(mod.convert(_API, _STAMP))
    data = json.loads(text)

    assert data["schema_version"] == 1
    assert data["source"]["repo_commit"] == "0620137a"
    assert data["source"]["license"] == "MIT"
    assert list(data["models"]) == sorted(data["models"])
    assert text == mod.render(json.loads(text))


def test_a_zero_limit_is_unknown_not_zero(mod: ModuleType) -> None:
    api = {"mistral": {"models": {"voxtral": {"limit": {"context": 0, "output": 0}}}}}

    assert mod.convert(api, _STAMP)["models"]["mistral/voxtral"] == {}


def test_main_writes_a_stamped_file_from_what_it_fetched(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = {
        mod.API_URL: (json.dumps(_API).encode(), '"etag-1"'),
        f"https://api.github.com/repos/{mod.REPO}/commits/{mod.BRANCH}": (b'{"sha": "c0ffee"}', ""),
        f"https://raw.githubusercontent.com/{mod.REPO}/c0ffee/LICENSE": (b"MIT License\n", ""),
    }
    monkeypatch.setattr(mod, "_get", replies.__getitem__)
    monkeypatch.setattr(mod, "OUTPUT", tmp_path / "models_dev.json")

    assert mod.main() == 0

    source = json.loads((tmp_path / "models_dev.json").read_text(encoding="utf-8"))["source"]
    assert (source["etag"], source["repo_commit"], source["license"]) == (
        '"etag-1"',
        "c0ffee",
        "MIT License",
    )
    assert source["fetched"]
