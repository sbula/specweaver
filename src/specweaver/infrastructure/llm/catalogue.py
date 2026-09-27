# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What each model costs and can do, from one shipped catalogue.

Three layers, lowest first, merged field by field:

1. `catalogue_data/models_dev.json` — generated from models.dev by `scripts/update_model_catalogue.py`,
   never edited by hand.
2. `catalogue_data/local.toml` — what models.dev lacks: per-kind facts and models on local servers.
3. `[models."<id>"]` in the machine settings file — the user's corrections.

Entries are keyed `"<kind>/<model>"`, so a model on a local (`openai-compatible`) server never takes
a hosted entry of the same name: the hosted price is wrong for your own hardware.
"""

from __future__ import annotations

import functools
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from specweaver.core.config.llm_settings import ModelFacts, SettingsFileError

if TYPE_CHECKING:
    from collections.abc import Mapping

CATALOGUE_DIR = Path(__file__).parent / "catalogue_data"
GENERATED_FILE = "models_dev.json"
LOCAL_FILE = "local.toml"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Catalogue:
    """Facts per `"<kind>/<model>"`, and per-kind defaults."""

    models: dict[str, ModelFacts]
    kinds: dict[str, ModelFacts]
    source: dict[str, Any]

    @classmethod
    def from_texts(cls, generated: str, local: str) -> Catalogue:
        generated_data = json.loads(generated)
        local_data = tomllib.loads(local)
        _check_version(generated_data, GENERATED_FILE)
        _check_version(local_data, LOCAL_FILE)
        models = _facts_table(generated_data.get("models", {}), GENERATED_FILE)
        local_models = local_data.get("models", {})
        for entry in local_models.values():
            entry.pop("note", None)  # for people, not for code
        for key, facts in _facts_table(local_models, LOCAL_FILE).items():
            models[key] = _combine(models[key], facts) if key in models else facts
        kinds = _facts_table(local_data.get("kinds", {}), LOCAL_FILE)
        return cls(models=models, kinds=kinds, source=generated_data.get("source", {}))

    def facts(
        self, kind: str, model: str, overrides: Mapping[str, ModelFacts]
    ) -> ModelFacts | None:
        """The model's facts on a server of this kind, or `None` if nothing is known about it."""
        known = self.models.get(f"{kind}/{model}")
        override = overrides.get(model)
        if known is None and override is None:
            return None
        return _merge(_merge(self.kinds.get(kind), known), override)


@functools.cache
def shipped_catalogue() -> Catalogue:
    """The catalogue shipped with SpecWeaver, read once per process."""
    return Catalogue.from_texts(
        (CATALOGUE_DIR / GENERATED_FILE).read_text(encoding="utf-8"),
        (CATALOGUE_DIR / LOCAL_FILE).read_text(encoding="utf-8"),
    )


def _check_version(data: dict[str, Any], source: str) -> None:
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SettingsFileError(
            source,
            "schema_version",
            0,
            f"catalogue schema {version}; this SpecWeaver reads {SCHEMA_VERSION} — update "
            "SpecWeaver or regenerate the catalogue",
        )


def _facts_table(entries: dict[str, Any], source: str) -> dict[str, ModelFacts]:
    table: dict[str, ModelFacts] = {}
    for key, entry in entries.items():
        try:
            table[key] = ModelFacts.model_validate(entry)
        except ValidationError as exc:
            error = exc.errors()[0]
            field = ".".join(str(part) for part in error["loc"])
            raise SettingsFileError(source, f"{key}.{field}", 0, error["msg"]) from None
    return table


def _merge(lower: ModelFacts | None, higher: ModelFacts | None) -> ModelFacts | None:
    if lower is None or higher is None:
        return higher or lower
    return _combine(lower, higher)


def _combine(lower: ModelFacts, higher: ModelFacts) -> ModelFacts:
    """Field by field; a field the higher layer leaves unset keeps the lower value."""
    return ModelFacts.model_validate(
        lower.model_dump(exclude_none=True) | higher.model_dump(exclude_none=True)
    )
