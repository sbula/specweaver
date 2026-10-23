# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a call with each role really sends, for `sw config show`.

The settings files alone cannot say it: the output limit and sampling may come from the catalogue,
and an adapter may never send a value a role sets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.adapters.registry import get_adapter_class
from specweaver.infrastructure.llm.resolve import _SAMPLING, DEFAULT_ROLE

if TYPE_CHECKING:
    from specweaver.core.config.llm_roles import ResolvedRole
    from specweaver.core.config.llm_settings import ModelFacts
    from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
    from specweaver.infrastructure.llm.catalogue import Catalogue

CATALOGUE = "catalogue"


def role_rows(
    files: LlmSettingsFiles, roles: dict[str, ResolvedRole], catalogue: Catalogue
) -> list[tuple[str, str, str]]:
    """Each role as (key, value, origin): its model, output limit and the sampling it sends."""
    rows: list[tuple[str, str, str]] = []
    if DEFAULT_ROLE not in roles:
        rows.append((f"roles.{DEFAULT_ROLE}", "unset — a role nobody set has no model", "-"))
    for role, setting in sorted(roles.items()):
        server = files.machine.servers[setting.server]
        facts = catalogue.facts(server.kind, setting.model, files.machine.models)
        key = f"roles.{role}"
        rows.append((key, f"{setting.model}@{setting.server}", setting.origin["model"]))
        rows.append(_output_limit_row(key, setting, facts))
        rows.extend(_sampling_rows(key, setting, facts, server.kind))
    return rows


def _output_limit_row(
    key: str, setting: ResolvedRole, facts: ModelFacts | None
) -> tuple[str, str, str]:
    name = f"{key}.max_output_tokens"
    if setting.max_output_tokens is not None:
        return (name, str(setting.max_output_tokens), setting.origin["max_output_tokens"])
    if facts is not None and facts.max_output is not None:
        return (name, str(facts.max_output), CATALOGUE)
    return (name, "unknown — a call with this role is refused", "-")


def _sampling_rows(
    key: str, setting: ResolvedRole, facts: ModelFacts | None, kind: str
) -> list[tuple[str, str, str]]:
    """The role's sampling, else the catalogue's, saying which values the adapter never sends."""
    shipped = facts.sampling if facts is not None else None
    sent = get_adapter_class(kind).sent_sampling
    rows: list[tuple[str, str, str]] = []
    for name in _SAMPLING:
        value, origin = getattr(setting, name), setting.origin.get(name, "")
        if value is None and shipped is not None:
            value, origin = getattr(shipped, name), CATALOGUE
        if value is None:
            continue
        shown = str(value) if name in sent else f"{value} — not sent: {kind} ignores it"
        rows.append((f"{key}.{name}", shown, origin))
    return rows
