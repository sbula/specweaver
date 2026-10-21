# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a spec review knows of the project's other specs, and which conflicts it can prove."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from specweaver.commons.spec_names import module_stem

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)

_REQUIREMENT_ROW = re.compile(r"^\|\s*((?:N)?FR-\d+[a-z]?)\s*\|\s*([^|\n]*)\|", re.MULTILINE)
_NAMED_FILE = re.compile(r"[\w./-]+\.(?:md|py|java|kt|ts|rs)\b")
_QUOTE = re.compile(r'"([^"\n]+)"')
_CONFLICT = "CONFLICT:"
#: A map line is a pointer, not the spec: the repo's own line limit for documents.
_PURPOSE_CHARS = 200


def _other_specs(context: RunContext) -> list[Path]:
    folder = context.project_path / "specs"
    mine = context.spec_path.resolve()
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob("*_spec.md") if p.resolve() != mine)


def _summary(path: Path, root: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines()]
    title = next((line[2:] for line in lines if line.startswith("# ")), path.stem)
    first = next((line for line in lines if line and not line.startswith(("#", "|", "`"))), "")
    purpose = first.split(". ", 1)[0][:_PURPOSE_CHARS]
    requirements = [f"{rid} {name.strip()}" for rid, name in _REQUIREMENT_ROW.findall(text)]
    return (
        f"- {path.relative_to(root).as_posix()}: {title} — {purpose}\n"
        f"  requirements: {', '.join(requirements) or 'none'}"
    )


def spec_map(context: RunContext) -> str:
    """One entry per other spec: path, title, purpose and requirement titles."""
    entries = [_summary(path, context.project_path) for path in _other_specs(context)]
    if not entries:
        return "The project has no other spec."
    return (
        "Read in full every spec below that touches the same behaviour, and the contracts and code "
        "they name, before you judge consistency.\n" + "\n".join(entries)
    )


def _methods_in(text: str, *, code: bool) -> dict[str, str]:
    from specweaver.core.flow.handlers.contract_renderers import extract_contract, extract_methods

    section = f"```python\n{text}\n```" if code else extract_contract(text) or ""
    methods: dict[str, str] = {}
    for method in extract_methods(section):
        owner = (method.owner or "").removesuffix("Protocol")
        methods[f"{owner}.{method.name}" if owner else method.name] = method.signature
    return methods


def signature_conflicts(context: RunContext) -> list[str]:
    """A contract method this spec declares with other parameters than another spec or contract."""
    try:
        mine = _methods_in(context.spec_path.read_text(encoding="utf-8"), code=False)
    except OSError as exc:
        logger.debug("The spec is unreadable, so no signature conflicts are checked: %s", exc)
        return []
    others = [(p, False) for p in _other_specs(context)]
    contracts = context.project_path / "contracts"
    own_contract = f"{module_stem(context.spec_path)}_contract"
    if contracts.is_dir():
        others += [(p, True) for p in sorted(contracts.glob("*.py")) if p.stem != own_contract]
    found = []
    for path, code in others:
        theirs = _methods_in(path.read_text(encoding="utf-8", errors="replace"), code=code)
        for name, signature in theirs.items():
            if name in mine and " ".join(signature.split()) != " ".join(mine[name].split()):
                where = path.relative_to(context.project_path).as_posix()
                found.append(
                    f"{_CONFLICT} {name} is `{mine[name]}` here and `{signature}` in {where}"
                )
    return found


def proven(message: str, context: RunContext) -> bool:
    """A conflict counts when a project file it names holds one of the texts it quotes."""
    root = context.project_path.resolve()
    quotes = _QUOTE.findall(message)
    for name in _NAMED_FILE.findall(message):
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(quote in text for quote in quotes):
            return True
    return False


def is_conflict(message: str) -> bool:
    return message.strip().upper().startswith(_CONFLICT)
