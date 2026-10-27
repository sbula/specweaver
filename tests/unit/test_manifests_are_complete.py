# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every module manifest says what the module is, and exposes only what exists.

Proves: TECH-081 FR-6, TECH-081 FR-8

| Bucket | Case |
|---|---|
| Happy | every `context.yaml` has `name`, `purpose` and `archetype` |
| Boundary | an `exposes` entry may be a file, a folder, a glob, or a name the package defines or imports |
| Degradation | an empty manifest reports its missing fields instead of crashing |
| Hostile | an `exposes` entry that climbs out of the package (`../x`) does not count |
"""

from __future__ import annotations

import re
from pathlib import Path

from ruamel.yaml import YAML

_SRC = Path(__file__).resolve().parents[2] / "src" / "specweaver"
_FIELDS = ("name", "purpose", "archetype")


def _load(manifest: Path) -> dict:
    return YAML(typ="safe").load(manifest.read_text(encoding="utf-8")) or {}


def _manifests() -> list[Path]:
    return sorted(_SRC.rglob("context.yaml"))


def _missing_fields(data: dict) -> list[str]:
    return [field for field in _FIELDS if not str(data.get(field) or "").strip()]


def _exists(package: Path, entry: str) -> bool:
    if ".." in Path(entry).parts:
        return False
    if any(package.glob(entry)):
        return True
    as_path = package / entry.replace(".", "/")
    if as_path.is_dir() or as_path.with_suffix(".py").exists():
        return True
    name = re.escape(entry.split(".")[-1])
    bound = re.compile(
        rf"^\s*(?:(?:async\s+)?def|class)\s+{name}\b|^\s*{name}\s*[:=]|^\s*(?:from\s+\S+\s+)?import\b.*\b{name}\b",
        re.M,
    )
    return any(bound.search(f.read_text(encoding="utf-8")) for f in package.rglob("*.py"))


def test_every_manifest_names_its_purpose_and_archetype() -> None:
    incomplete = {
        str(m.relative_to(_SRC)): missing
        for m in _manifests()
        if (missing := _missing_fields(_load(m)))
    }

    assert incomplete == {}


def test_every_exposed_name_exists() -> None:
    phantoms = [
        f"{m.relative_to(_SRC)}: {entry}"
        for m in _manifests()
        for entry in (_load(m).get("exposes") or [])
        if not _exists(m.parent, str(entry))
    ]

    assert phantoms == []


#: `context_yaml_spec.md` "Built-in archetypes", plus `data` (`archetypes.md`).
_ARCHETYPES = {
    "pure-logic",
    "adapter",
    "facade",
    "contract",
    "entry-point",
    "orchestrator",
    "store",
    "mixed",
    "data",
}


def test_every_archetype_is_one_the_spec_defines() -> None:
    unknown = {
        str(m.relative_to(_SRC)): data.get("archetype")
        for m in _manifests()
        if (data := _load(m)).get("archetype") not in _ARCHETYPES
    }

    assert unknown == {}


def test_a_module_that_calls_the_web_is_an_adapter() -> None:
    assert _load(_SRC / "sandbox/web/interfaces/context.yaml")["archetype"] == "adapter"


def test_an_empty_manifest_reports_every_field(tmp_path: Path) -> None:
    manifest = tmp_path / "context.yaml"
    manifest.write_text("", encoding="utf-8")

    assert _missing_fields(_load(manifest)) == list(_FIELDS)


def test_an_entry_outside_the_package_does_not_count(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "secret.py").write_text("token = 1\n", encoding="utf-8")

    assert _exists(tmp_path / "pkg", "../secret.py") is False


def test_a_reexported_name_counts(tmp_path: Path) -> None:
    (tmp_path / "_core.py").write_text("from x.db import get_db\n", encoding="utf-8")

    assert _exists(tmp_path, "get_db") is True
    assert _exists(tmp_path, "get_nothing") is False
