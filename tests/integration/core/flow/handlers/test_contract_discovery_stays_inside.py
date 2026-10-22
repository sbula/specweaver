# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C13's contract discovery reads only contracts inside the project.

Proves: TECH-075 FR-4
Proves: TECH-075 NFR-3

`discover_protocol_endpoints` walks the project and hands each contract to the real
`ProtocolAtom`. A link inside the project that points outside is skipped with a warning, and its
target is never read, not even to sniff whether it is a contract.

| Bucket | Case |
|---|---|
| Happy | a contract in the project gives its endpoints |
| Boundary | a link that points inside the project is read |
| Degradation | a skipped link is named in a WARNING, the run goes on |
| Hostile | a link to an outside contract gives nothing and is never opened |
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from specweaver.core.flow.handlers.validation_hydrator import discover_protocol_endpoints

_CONTRACT = "openapi: 3.0.3\npaths:\n  /{name}:\n    get:\n      operationId: {name}\n"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "api.yaml").write_text(_CONTRACT.format(name="own"), encoding="utf-8")
    (root / "real.yaml").write_text(_CONTRACT.format(name="inner"), encoding="utf-8")
    (outside / "api.yaml").write_text(_CONTRACT.format(name="secret"), encoding="utf-8")
    (root / "alias.yaml").symlink_to(root / "real.yaml")
    (root / "escape.yaml").symlink_to(outside / "api.yaml")
    return root


def _paths(endpoints: list[dict[str, str]]) -> set[str]:
    return {e["path"] for e in endpoints}


def test_contracts_inside_are_read_and_a_link_out_is_not(project: Path) -> None:
    assert _paths(discover_protocol_endpoints(project)) == {"/own", "/inner"}


def test_the_skipped_link_is_named_in_a_warning(
    project: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        discover_protocol_endpoints(project)
    assert any("escape.yaml" in r.getMessage() for r in caplog.records)


def test_the_outside_target_is_never_opened(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outside = (project.parent / "outside").resolve()
    real_read_text = Path.read_text
    opened: list[Path] = []

    def spy(self: Path, *args: object, **kwargs: object) -> str:
        opened.append(self.resolve())
        return real_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", spy)
    discover_protocol_endpoints(project)
    assert not [p for p in opened if p.is_relative_to(outside)]


def test_a_link_out_that_is_no_contract_is_skipped_quietly(
    project: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (project.parent / "outside" / "shared.py").write_text("x = 1\n", encoding="utf-8")
    (project / "shared.py").symlink_to(project.parent / "outside" / "shared.py")
    with caplog.at_level(logging.WARNING):
        discover_protocol_endpoints(project)
    assert not any("shared.py" in r.getMessage() for r in caplog.records)
