# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`scripts/stale_mutants.py`: every mutant whose code moved, across all corpora.

| Bucket | Case |
|---|---|
| Happy | a mutant whose symbol still hashes the same is not listed; a moved one is |
| Boundary | an unhashed mutant is not STALE; a retired campaign is skipped |
| Degradation | a mutant whose file is gone is STALE, not a crash |
| Hostile | an unreadable corpus is reported by name with exit 2 |
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_corpus = _load("_corpus")

SOURCE = "def target():\n    return 1\n"


@pytest.fixture(scope="module")
def sm() -> ModuleType:
    return _load("stale_mutants")


def _mutant(mid: str, sha: str | None, file: str = "mod.py") -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": mid,
        "origin": "authored",
        "file": file,
        "symbol": "target",
        "old": "return 1",
        "new": "return 2",
        "breaks": "x",
    }
    if sha is not None:
        entry["symbol_sha"] = sha
    return entry


def _corpus_file(root: Path, campaigns: list[dict[str, Any]]) -> Path:
    path = root / "TECH-901" / "TECH-901_mutants.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"schema": _corpus.SCHEMA, "feature": "TECH-901", "campaigns": campaigns}),
        encoding="utf-8",
    )
    return path


def _campaign(req: str, mutants: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {"requirement": req, "scope": ["tests/x.py"], "mutants": mutants, **extra}


class TestStale:
    def test_only_the_moved_mutant_is_listed(self, sm: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text(SOURCE, encoding="utf-8")
        good = _corpus.symbol_sha(SOURCE, "target")
        path = _corpus_file(
            tmp_path,
            [_campaign("FR-1", [_mutant("still-here", good), _mutant("moved", "sha256:0")])],
        )
        assert sm.stale([path], tmp_path) == [f"{path} FR-1 moved"]

    def test_unhashed_and_retired_are_not_listed(self, sm: ModuleType, tmp_path: Path) -> None:
        (tmp_path / "mod.py").write_text(SOURCE, encoding="utf-8")
        path = _corpus_file(
            tmp_path,
            [
                _campaign("FR-1", [_mutant("unhashed", None)]),
                _campaign("FR-2", [_mutant("old", "sha256:0")], retired={"reason": "gone"}),
            ],
        )
        assert sm.stale([path], tmp_path) == []

    def test_a_vanished_file_is_stale_not_a_crash(self, sm: ModuleType, tmp_path: Path) -> None:
        path = _corpus_file(tmp_path, [_campaign("FR-1", [_mutant("gone", "sha256:0", "no.py")])])
        assert sm.stale([path], tmp_path) == [f"{path} FR-1 gone"]


class TestMain:
    def test_exit_1_and_a_line_per_stale_mutant(
        self, sm: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _corpus_file(tmp_path, [_campaign("FR-1", [_mutant("gone", "sha256:0", "no.py")])])
        assert sm.main(["--features", str(tmp_path), "--root", str(tmp_path)]) == 1
        assert "FR-1 gone" in capsys.readouterr().out

    def test_exit_0_when_nothing_is_stale(
        self, sm: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert sm.main(["--features", str(tmp_path), "--root", str(tmp_path)]) == 0
        assert "0 stale" in capsys.readouterr().out

    def test_an_unreadable_corpus_is_named_with_exit_2(
        self, sm: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_path / "TECH-902" / "TECH-902_mutants.json"
        bad.parent.mkdir()
        bad.write_text("{not json", encoding="utf-8")
        assert sm.main(["--features", str(tmp_path), "--root", str(tmp_path)]) == 2
        assert "TECH-902_mutants.json" in capsys.readouterr().err
