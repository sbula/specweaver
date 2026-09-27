#!/usr/bin/env python
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Regenerate the shipped model catalogue from models.dev.

    python scripts/update_model_catalogue.py

models.dev builds its `api.json` at deploy time and commits none, so no commit can be pinned. The
committed output is the pin instead: it is stamped with the fetch date, the ETag and the repository
head at that moment, and its diff is the review. SpecWeaver never fetches it at runtime.

Kept: the five hosted providers SpecWeaver has adapters for, under SpecWeaver's kind names, without
deprecated models. Qwen comes from `alibaba-cn`, whose address is the Qwen adapter's default.
Local additions live in `catalogue_data/local.toml`, which this script never touches.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

API_URL = "https://models.dev/api.json"
REPO = "anomalyco/models.dev"
BRANCH = "dev"
OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "src/specweaver/infrastructure/llm/catalogue_data/models_dev.json"
)
SCHEMA_VERSION = 1

#: models.dev provider id → SpecWeaver server kind.
PROVIDERS = {
    "google": "gemini",
    "openai": "openai",
    "anthropic": "anthropic",
    "mistral": "mistral",
    "alibaba-cn": "qwen",
}

_HEADERS = {"User-Agent": "specweaver-catalogue-update"}


def convert(api: dict[str, Any], stamp: dict[str, str]) -> dict[str, Any]:
    """The catalogue for `api.json`: our kinds only, no deprecated models, prices per 1M tokens."""
    models: dict[str, dict[str, Any]] = {}
    for provider, kind in PROVIDERS.items():
        for model_id, model in api.get(provider, {}).get("models", {}).items():
            if model.get("status") == "deprecated":
                continue
            models[f"{kind}/{model_id}"] = _facts(model)
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"url": API_URL, **stamp},
        "models": models,
    }


def _facts(model: dict[str, Any]) -> dict[str, Any]:
    cost = model.get("cost", {})
    limit = model.get("limit", {})
    facts = {
        # models.dev writes 0 where a limit does not apply (audio, embeddings): unknown, not zero.
        "context": limit.get("context") or None,
        "max_output": limit.get("output") or None,
        "tool_calls": model.get("tool_call"),
        "usd_per_million_input": cost.get("input"),
        "usd_per_million_output": cost.get("output"),
    }
    return {key: value for key, value in facts.items() if value is not None}


def render(catalogue: dict[str, Any]) -> str:
    """Sorted and indented, so a rerun with no upstream change leaves no diff."""
    return json.dumps(catalogue, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _get(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get("ETag", "")


def main() -> int:
    body, etag = _get(API_URL)
    head, _ = _get(f"https://api.github.com/repos/{REPO}/commits/{BRANCH}")
    commit = json.loads(head)["sha"]
    licence, _ = _get(f"https://raw.githubusercontent.com/{REPO}/{commit}/LICENSE")
    stamp = {
        "fetched": datetime.now(UTC).date().isoformat(),
        "etag": etag,
        "repo_commit": commit,
        "license": licence.decode("utf-8").strip(),
    }
    catalogue = convert(json.loads(body), stamp)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(catalogue), encoding="utf-8")
    print(f"{len(catalogue['models'])} models written to {OUTPUT} (models.dev {commit[:8]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
