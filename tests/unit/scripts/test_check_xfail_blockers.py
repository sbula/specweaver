# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the stale-xfail guard (`scripts/check_xfail_blockers.py`).

`ADR-004` clause 4: a test is written as soon as the interface it exercises is defined, not when the
implementation lands. Where the implementation is absent it is committed as
`pytest.mark.xfail(strict=True)` naming the blocking capability, so it fails first and proves it
tests the path at the moment it turns green.

Two ways that decays, and this guard closes both:

* **The blocker ships and the marker stays.** `strict=True` means an unexpected pass is a failure,
  so the suite does complain — but only once someone reads it as "the marker is stale" rather than
  "the test is broken". The registry knows the answer: the capability is `✅` in the matrix.
* **The marker names no blocker.** Then nothing can ever tell whether it is stale, which is how
  every suppression list in this repo decayed. Requiring a named blocker makes the reason part of
  the contract rather than a convention.

Zero-tolerance: clause 4's markers do not exist yet, so there is no legacy set.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cxb() -> ModuleType:
    return _load("check_xfail_blockers")


MATRIX = """# Capability Matrix

| DAL | Flow |
|---|---|
| **DAL-C** | `✅ C-FLOW-05`: Shipped<br>`🔜 C-FLOW-11`: Unbuilt<br>`🔮 B-INTL-08`: Visionary |
"""


def _tree(root: Path, tests: dict[str, str]) -> tuple[Path, Path]:
    """A throwaway repo: a capability matrix and a `tests/` tree."""
    roadmap = root / "docs" / "roadmap"
    roadmap.mkdir(parents=True)
    (roadmap / "capability_matrix.md").write_text(MATRIX, encoding="utf-8")
    tests_root = root / "tests"
    for rel, body in tests.items():
        path = tests_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    tests_root.mkdir(exist_ok=True)
    return roadmap, tests_root


def _marker(blocker: str, *, strict: bool = True) -> str:
    return (
        "import pytest\n\n\n"
        f'@pytest.mark.xfail(strict={strict}, reason="blocked on {blocker} — not built yet")\n'
        "def test_the_journey() -> None:\n"
        "    assert False\n"
    )


class TestStaleMarkers:
    """A strict xfail whose named blocker has shipped."""

    def test_a_shipped_blocker_is_reported(self, cxb: ModuleType, tmp_path: Path) -> None:
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": _marker("C-FLOW-05")})
        found = cxb.stale_markers(roadmap, tests_root)
        assert len(found) == 1
        assert found[0].blocker == "C-FLOW-05"

    def test_an_unbuilt_blocker_passes(self, cxb: ModuleType, tmp_path: Path) -> None:
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": _marker("C-FLOW-11")})
        assert cxb.stale_markers(roadmap, tests_root) == []

    def test_a_visionary_blocker_passes(self, cxb: ModuleType, tmp_path: Path) -> None:
        """`🔮` is unbuilt too — the marker is honest until the capability actually ships."""
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": _marker("B-INTL-08")})
        assert cxb.stale_markers(roadmap, tests_root) == []

    def test_a_non_strict_xfail_is_out_of_scope(self, cxb: ModuleType, tmp_path: Path) -> None:
        """Only `strict=True` carries the clause-4 promise; a lenient xfail makes no claim to judge."""
        body = _marker("C-FLOW-05", strict=False)
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": body})
        assert cxb.stale_markers(roadmap, tests_root) == []

    def test_a_blocker_absent_from_the_matrix_is_reported(
        self, cxb: ModuleType, tmp_path: Path
    ) -> None:
        """A dangling reference is a finding, not a pass — `TECH-032`'s lesson."""
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": _marker("C-NOPE-99")})
        found = cxb.stale_markers(roadmap, tests_root)
        assert [f.status for f in found] == ["?"]

    def test_the_message_names_the_file_and_line(self, cxb: ModuleType, tmp_path: Path) -> None:
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": _marker("C-FLOW-05")})
        (finding,) = cxb.stale_markers(roadmap, tests_root)
        assert finding.path.endswith("test_a.py")
        assert finding.line == 4


class TestStaleMarkersWithNoNamedBlocker:
    """A strict xfail whose reason names no capability cannot ever be judged stale."""

    def test_a_reason_naming_no_blocker_is_reported(self, cxb: ModuleType, tmp_path: Path) -> None:
        body = (
            "import pytest\n\n\n"
            '@pytest.mark.xfail(strict=True, reason="not implemented")\n'
            "def test_the_journey() -> None:\n"
            "    assert False\n"
        )
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": body})
        found = cxb.stale_markers(roadmap, tests_root)
        assert [f.blocker for f in found] == ["(none named)"]

    def test_a_missing_reason_is_reported(self, cxb: ModuleType, tmp_path: Path) -> None:
        body = (
            "import pytest\n\n\n"
            "@pytest.mark.xfail(strict=True)\n"
            "def test_the_journey() -> None:\n"
            "    assert False\n"
        )
        roadmap, tests_root = _tree(tmp_path, {"e2e/test_a.py": body})
        found = cxb.stale_markers(roadmap, tests_root)
        assert [f.blocker for f in found] == ["(none named)"]


class TestMain:
    """The CLI contract `quality.py` depends on: 0 clean, 1 on findings, 2 cannot run."""

    def test_exits_one_and_names_the_offender(
        self, cxb: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _tree(tmp_path, {"e2e/test_a.py": _marker("C-FLOW-05")})
        assert cxb.main(["--root", str(tmp_path)]) == 1
        assert "C-FLOW-05" in capsys.readouterr().out

    def test_exits_zero_when_every_blocker_is_unbuilt(
        self, cxb: ModuleType, tmp_path: Path
    ) -> None:
        _tree(tmp_path, {"e2e/test_a.py": _marker("C-FLOW-11")})
        assert cxb.main(["--root", str(tmp_path)]) == 0

    def test_exits_two_without_a_matrix(self, cxb: ModuleType, tmp_path: Path) -> None:
        assert cxb.main(["--root", str(tmp_path)]) == 2

    def test_the_live_repo_passes(self, cxb: ModuleType) -> None:
        """Zero-tolerance — clause 4's markers do not exist yet, so there is no legacy set."""
        assert cxb.main([]) == 0
