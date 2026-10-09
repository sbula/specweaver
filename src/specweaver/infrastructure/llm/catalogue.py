# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What each model costs and can do: one short shipped list, corrected by the machine file.

1. `catalogue_data/models.toml` — the models SpecWeaver is used with, edited by hand.
2. `[models."<id>"]` in the machine settings file — the user's own prices and corrections.

Entries are keyed `"<kind>/<model>"`, so a model on a local (`openai-compatible`) server never takes
a hosted entry of the same name: the hosted price is wrong for your own hardware.
"""

from __future__ import annotations

import functools
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from specweaver.core.config.llm_settings import ModelFacts, SettingsFileError

if TYPE_CHECKING:
    from collections.abc import Mapping

CATALOGUE_FILE = Path(__file__).parent / "catalogue_data" / "models.toml"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Catalogue:
    """Facts per `"<kind>/<model>"`, per-kind defaults, and the date the prices were checked."""

    models: dict[str, ModelFacts]
    kinds: dict[str, ModelFacts]
    checked: str

    @classmethod
    def from_text(cls, text: str, source: str = CATALOGUE_FILE.name) -> Catalogue:
        data = tomllib.loads(text)
        _check_version(data, source)
        models = data.get("models", {})
        for entry in models.values():
            entry.pop("note", None)  # for people, not for code
        return cls(
            models=_facts_table(models, source),
            kinds=_facts_table(data.get("kinds", {}), source),
            checked=str(data.get("checked", "unknown")),
        )

    def facts(
        self, kind: str, model: str, overrides: Mapping[str, ModelFacts]
    ) -> ModelFacts | None:
        """The model's facts on a server of this kind, or `None` if nothing is known about it.

        A machine entry named `"<kind>/<model>"` applies to that kind only, over a bare `"<model>"`.
        """
        known = self.models.get(f"{kind}/{model}")
        override = _merge(overrides.get(model), overrides.get(f"{kind}/{model}"))
        if known is None and override is None:
            return None
        return _merge(_merge(self.kinds.get(kind), known), override)


@functools.cache
def shipped_catalogue() -> Catalogue:
    """The list shipped with SpecWeaver, read once per process."""
    return Catalogue.from_text(CATALOGUE_FILE.read_text(encoding="utf-8"))


def _check_version(data: dict[str, Any], source: str) -> None:
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SettingsFileError(
            source,
            "schema_version",
            0,
            f"catalogue schema {version}; this SpecWeaver reads {SCHEMA_VERSION} — update "
            "SpecWeaver",
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
