# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What each model costs and can do: one short shipped list, corrected by the machine file.

1. `catalogue_data/models.toml` — the models SpecWeaver is used with, edited by hand.
2. `[models."<id>"]` in the machine settings file — the user's own prices and corrections.

A model's `specials` are prices that apply only while their rule holds, such as a cached read; the
list is the only source of these rules, as the providers publish them only as prose.

Entries are keyed `"<kind>/<model>"`, so a model on a local (`openai-compatible`) server never takes
a hosted entry of the same name: the hosted price is wrong for your own hardware.
"""

from __future__ import annotations

import functools
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from specweaver.core.config.llm_settings import ModelFacts, SettingsFileError
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.prices import SETTING_OF, Price, Rule

if TYPE_CHECKING:
    from collections.abc import Mapping

CATALOGUE_FILE = Path(__file__).parent / "catalogue_data" / "models.toml"
SCHEMA_VERSION = 1


class _Special(BaseModel):
    """One line of a model's `specials`: a price and the rule under which it applies."""

    model_config = ConfigDict(extra="forbid")

    kind: TokenKind
    usd_per_million: float = Field(ge=0, allow_inf_nan=False)
    min_prefix_tokens: int | None = Field(default=None, ge=1)
    max_age_seconds: int | None = Field(default=None, ge=1)
    min_prompt_tokens: int | None = Field(default=None, ge=1)
    requires: str = "nothing"


@dataclass(frozen=True)
class Catalogue:
    """Facts per `"<kind>/<model>"`, per-kind defaults, and the date the prices were checked."""

    models: dict[str, ModelFacts]
    kinds: dict[str, ModelFacts]
    checked: str
    specials: dict[str, list[_Special]] = field(default_factory=dict)

    @classmethod
    def from_text(cls, text: str, source: str = CATALOGUE_FILE.name) -> Catalogue:
        data = tomllib.loads(text)
        _check_version(data, source)
        models = data.get("models", {})
        specials = {key: entry.pop("specials", []) for key, entry in models.items()}
        for entry in models.values():
            entry.pop("note", None)  # for people, not for code
        catalogue = cls(
            models=_facts_table(models, source),
            kinds=_facts_table(data.get("kinds", {}), source),
            checked=str(data.get("checked", "unknown")),
            specials={key: _specials(key, rows, source) for key, rows in specials.items()},
        )
        return catalogue

    def prices(self, kind: str, model: str) -> list[Price]:
        """The listed prices of the model on a server of this kind, valid from the check date — or
        from always, for a list that names none."""
        key = f"{kind}/{model}"
        facts = self.models.get(key)
        if facts is None:
            return []
        try:
            day = date.fromisoformat(self.checked)
        except ValueError:  # expected: a list with no check date holds from always
            day = date.min
        prices = [
            Price(kind=token, usd_per_million=usd, valid_from=day, source="catalogue")
            for token, name in SETTING_OF.items()
            if (usd := getattr(facts, name)) is not None
        ]
        prices += [_price(special, day) for special in self.specials.get(key, [])]
        return prices

    def facts(
        self, kind: str, model: str, overrides: Mapping[str, ModelFacts]
    ) -> ModelFacts | None:
        """The model's facts on a server of this kind, or `None` if nothing is known about it.

        A machine entry named `"<kind>/<model>"` applies to that kind only, over a bare `"<model>"`.
        """
        known = self.models.get(f"{kind}/{model}")
        override = corrections(kind, model, overrides)
        if known is None and override is None:
            return None
        return _merge(_merge(self.kinds.get(kind), known), override)


def corrections(kind: str, model: str, overrides: Mapping[str, ModelFacts]) -> ModelFacts | None:
    """The machine file's facts for the model: `"<kind>/<model>"` over a bare `"<model>"`."""
    return _merge(overrides.get(model), overrides.get(f"{kind}/{model}"))


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


def _specials(key: str, rows: list[Any], source: str) -> list[_Special]:
    specials: list[_Special] = []
    for index, row in enumerate(rows):
        try:
            specials.append(_Special.model_validate(row))
        except ValidationError as exc:
            error = exc.errors()[0]
            where = ".".join(str(part) for part in error["loc"])
            raise SettingsFileError(
                source, f"{key}.specials.{index}.{where}", 0, error["msg"]
            ) from None
    return specials


def _price(special: _Special, day: date) -> Price:
    rule = Rule(
        min_prefix_tokens=special.min_prefix_tokens,
        max_age_seconds=special.max_age_seconds,
        min_prompt_tokens=special.min_prompt_tokens,
        requires=special.requires,
    )
    return Price(special.kind, special.usd_per_million, day, "catalogue", rule)


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
