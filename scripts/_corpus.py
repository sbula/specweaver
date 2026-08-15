#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The mutation campaign corpus — the durable record of what each requirement is measured by.

`_mutate.py` answers one question and `_mutate_campaign.py` asks a list of them, but both take
their input from a JSON file authored once and thrown away. Nothing survives a run, so the question
that matters — *was this requirement protected last month and is it still?* — cannot be asked at
all. This module is the persistent half: a per-feature corpus, version-controlled beside the design
it tests.

## Shape

One file per **feature**, named `<ID>_mutants.json`, holding one **campaign** per (N)FR, each
holding several **mutants** that try to break that one requirement. Per-requirement files were
rejected on arithmetic: 575 requirements exist today and ~1,400 will at full roadmap, against 55
feature files now and ~149 then.

## Two rules that are not obvious

**The mutant id is derived, never taken.** `<feature> <requirement> <id>` is the identity that
recurrence counts and override entries use to name the same mutant across runs, and a hand-typed
one drifts the moment somebody renames a campaign.

**`feature` must match the filename.** That is the whole reason the duplicate-id check can read one
file instead of the corpus: two files cannot claim the same feature, so a collision across files is
impossible by construction rather than by luck.

## What this module does NOT do

It runs nothing. No sandbox, no pytest, no verdicts — it produces validated objects and drift state
for the runner to execute and the evaluator to judge. Validation happens **before** any sandbox
exists, which is the order `load_campaign` established for a reason: building a worktree to
discover a typo is a minute wasted per mistake.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Corpus format version. Bumped only when a change would make an older file misread rather than
#: merely incomplete — a reader that guesses at an unknown shape is how a silent misparse starts.
SCHEMA = 1

_MUTANT_KEYS = ("id", "file", "symbol", "old", "new", "breaks")
_CAMPAIGN_KEYS = ("requirement", "scope", "mutants")
_SUFFIX = "_mutants.json"


class CorpusError(Exception):
    """A corpus file that cannot be trusted, with enough context to find the offending entry.

    Every message names the file, and where the fault is inside one, the campaign and the mutant
    too. A bare "missing key" costs the reader a search through a forty-mutant file, which is the
    kind of friction that stops a corpus being maintained.
    """


@dataclass(frozen=True)
class Mutant:
    """One deliberate edit that should break exactly one requirement."""

    id: str
    file: str
    symbol: str
    old: str
    new: str
    breaks: str
    derived_id: str
    symbol_sha: str | None = None


@dataclass(frozen=True)
class Campaign:
    """The mutants for one (N)FR, and the tests they are judged against."""

    requirement: str
    scope: list[str]
    mutants: list[Mutant]
    title: str = ""
    retired: dict[str, Any] | None = None


@dataclass(frozen=True)
class Corpus:
    """One feature's campaigns, as loaded from its `<ID>_mutants.json`."""

    feature: str
    campaigns: list[Campaign]
    path: Path = field(default_factory=Path)


def feature_of(path: Path) -> str:
    """The feature id a corpus file's name declares.

    The filename is the authority rather than the directory, so a fixture in a temporary directory
    is as loadable as the real thing — a validation rule that can only be exercised inside the real
    tree is a rule that goes untested.
    """
    name = path.name
    if not name.endswith(_SUFFIX):
        raise CorpusError(f"{name}: a corpus file must be named <FEATURE-ID>{_SUFFIX}")
    return name[: -len(_SUFFIX)]


def _require(where: str, data: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        if key not in data or data[key] in (None, "", [], {}):
            raise CorpusError(f"{where}: missing or empty {key!r}")


def _read(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusError(f"{path.name}: cannot read — {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorpusError(f"{path.name}: not valid JSON — {exc}") from exc
    if not isinstance(parsed, dict):
        raise CorpusError(f"{path.name}: expected an object at the top level")
    return parsed


def _mutant_from(raw: dict[str, Any], *, where: str, feature: str, requirement: str) -> Mutant:
    _require(where, raw, _MUTANT_KEYS)
    if raw["old"] == raw["new"]:
        raise CorpusError(
            f"{where}: 'old' and 'new' are identical — that mutates nothing, so the run would "
            "report a survival that means the opposite of what it says"
        )
    return Mutant(
        id=raw["id"],
        file=raw["file"],
        symbol=raw["symbol"],
        old=raw["old"],
        new=raw["new"],
        breaks=raw["breaks"],
        derived_id=f"{feature} {requirement} {raw['id']}",
        symbol_sha=raw.get("symbol_sha"),
    )


def _campaign_from(raw: dict[str, Any], *, path: Path, feature: str) -> Campaign:
    if not isinstance(raw, dict):
        raise CorpusError(f"{path.name}: every campaign must be an object")
    requirement = raw.get("requirement") or "<unnamed campaign>"
    where = f"{path.name} :: {requirement}"
    _require(where, raw, _CAMPAIGN_KEYS)

    mutants = []
    for entry in raw["mutants"]:
        if not isinstance(entry, dict):
            raise CorpusError(f"{where}: every mutant must be an object")
        local = entry.get("id") or "<unnamed mutant>"
        mutants.append(
            _mutant_from(
                entry,
                where=f"{where} :: {local}",
                feature=feature,
                requirement=raw["requirement"],
            )
        )

    return Campaign(
        requirement=raw["requirement"],
        scope=list(raw["scope"]),
        mutants=mutants,
        title=raw.get("title", ""),
        retired=raw.get("retired"),
    )


def load_corpus(path: Path) -> Corpus:
    """Parse and validate one corpus file, or refuse it with the offending entry named.

    Ordered cheapest-first on purpose: a malformed file never reaches the filesystem or the AST
    parser, so a typo costs a parse rather than a worktree.
    """
    feature = feature_of(path)
    data = _read(path)

    schema = data.get("schema")
    if schema != SCHEMA:
        raise CorpusError(
            f"{path.name}: unknown schema {schema!r} (this reader understands {SCHEMA})"
        )

    declared = data.get("feature")
    if declared != feature:
        raise CorpusError(
            f"{path.name}: declares feature {declared!r} but its name says {feature!r}. "
            "They must agree — it is what keeps mutant ids unique without reading every file"
        )

    campaigns_raw = data.get("campaigns")
    if not isinstance(campaigns_raw, list) or not campaigns_raw:
        raise CorpusError(f"{path.name}: 'campaigns' must be a non-empty list")

    campaigns = [_campaign_from(entry, path=path, feature=feature) for entry in campaigns_raw]

    seen: dict[str, str] = {}
    for campaign in campaigns:
        for mutant in campaign.mutants:
            if mutant.derived_id in seen:
                raise CorpusError(
                    f"{path.name}: duplicate mutant id {mutant.derived_id!r}. Two mutants "
                    "answering to one identity collapse into each other across runs, so one "
                    "silently inherits the other's history"
                )
            seen[mutant.derived_id] = campaign.requirement

    return Corpus(feature=feature, campaigns=campaigns, path=path)
