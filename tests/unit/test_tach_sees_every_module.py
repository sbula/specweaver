# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The layer check sees every module, and every wrong edge it allows is owed by a named FR.

Proves: TECH-081 FR-1, TECH-081 FR-2, TECH-081 FR-3, TECH-081 FR-5

| Bucket | Case |
|---|---|
| Happy | `tach.toml` forbids code outside a module and checks type-only imports |
| Boundary | every `.py` file under `src/specweaver` falls in a registered module |
| Degradation | a ledger path that no longer exists is named |
| Hostile | a deprecated edge with no ledger row, or a row naming an FR the design lacks, fails |
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_TACH = _ROOT / "tach.toml"
_LEDGER = _ROOT / "docs/architecture/06_lessons_and_future/known_boundary_violations.md"
_DESIGN = _ROOT / "docs/roadmap/features/topic_07_technical_debt/TECH-081/TECH-081_design.md"
#: A row of the ledger's owed table: | `source` → `target` | ... | FR-n |
_OWED_ROW = re.compile(r"^\| `(specweaver[\w.]*)` → `(specweaver[\w.]*)` \|.*\| (FR-\d+) \|\s*$")


def _config() -> dict:
    with _TACH.open("rb") as f:
        return tomllib.load(f)


def _deprecated_edges() -> set[tuple[str, str]]:
    edges = set()
    for module in _config()["modules"]:
        for dep in module.get("depends_on", []):
            if isinstance(dep, dict) and dep.get("deprecated"):
                edges.add((module["path"], dep["path"]))
    return edges


def _owed_rows() -> dict[tuple[str, str], str]:
    rows = {}
    for line in _LEDGER.read_text(encoding="utf-8").splitlines():
        match = _OWED_ROW.match(line)
        if match:
            rows[(match[1], match[2])] = match[3]
    return rows


def test_code_outside_a_module_and_type_only_imports_are_checked() -> None:
    config = _config()

    assert config.get("root_module") == "forbid"
    assert config.get("ignore_type_checking_imports") is False


def test_every_source_file_belongs_to_a_registered_module() -> None:
    modules = [m["path"] for m in _config()["modules"]]
    stray = []
    for path in sorted((_ROOT / "src").rglob("*.py")):
        dotted = ".".join(path.with_suffix("").relative_to(_ROOT / "src").parts)
        dotted = dotted.removesuffix(".__init__")
        if not any(dotted == m or dotted.startswith(m + ".") for m in modules):
            stray.append(str(path.relative_to(_ROOT)))

    assert stray == [], f"files in no tach module: {stray}"


def test_every_deprecated_edge_is_owed_in_the_ledger() -> None:
    deprecated = _deprecated_edges()
    owed = _owed_rows()

    assert deprecated, "no deprecated edge: the owed list was dropped, not paid"
    assert deprecated - owed.keys() == set(), "deprecated edges with no ledger row"
    assert owed.keys() - deprecated == set(), "ledger rows whose edge is no longer deprecated"


def test_each_owed_edge_names_an_fr_of_the_design() -> None:
    design_frs = set(re.findall(r"^\| (FR-\d+) \|", _DESIGN.read_text(encoding="utf-8"), re.M))

    unknown = {edge: fr for edge, fr in _owed_rows().items() if fr not in design_frs}

    assert unknown == {}


def test_every_source_path_in_the_ledger_exists() -> None:
    cited = re.findall(r"`(src/specweaver/[\w/.]+?\.py)", _LEDGER.read_text(encoding="utf-8"))

    missing = sorted({p for p in cited if not (_ROOT / p).exists()})

    assert cited
    assert missing == []
