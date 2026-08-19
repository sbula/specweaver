# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly timer — the part of the system nobody invokes.

Proves: TECH-049 FR-10

A timer either fires or it does not, and that is not something a test can assert. What is
falsifiable: the units it generates are valid, the command line inside them actually runs, and
installing twice does not drift. Those three are what this file pins.

`Persistent=true` matters more than it looks — without it a machine that was off at 03:00 simply
skips that night, silently, and the corpus goes unmeasured exactly when nobody is watching.
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


@pytest.fixture(scope="module")
def mutation() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mutation", REPO_ROOT / "scripts" / "mutation.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["mutation"] = module
    spec.loader.exec_module(module)
    return module


class TestTimerUnits:
    """What the generated files say."""

    def test_the_service_runs_the_session_over_the_whole_corpus(self, mutation: ModuleType) -> None:
        service = mutation.timer_units()["service"]
        assert "mutation.py" in service
        assert "--corpus-dir" in service
        assert "Type=oneshot" in service, "oneshot stops a second run starting while one is going"

    def test_the_service_disables_colour(self, mutation: ModuleType) -> None:
        """The defect that started this ticket, in the one place nobody would look.

        A timer inherits whatever environment systemd gives it. If a future unit gained
        `FORCE_COLOR`, every nightly verdict would silently become SURVIVED again.
        """
        assert "PY_COLORS=0" in mutation.timer_units()["service"]

    def test_the_timer_is_nightly_and_persistent(self, mutation: ModuleType) -> None:
        timer = mutation.timer_units()["timer"]
        assert "OnCalendar=*-*-* 03:00" in timer
        assert "Persistent=true" in timer, "a machine off at 03:00 must run at next boot, not skip"

    def test_the_units_name_an_absolute_interpreter(self, mutation: ModuleType) -> None:
        """[Hostile] systemd has no PATH worth relying on; a bare `python` would find the wrong one.

        The project's own CLAUDE.md records a full suite run four times against the system
        interpreter before anyone noticed it lacked xdist. A timer would never notice at all.
        """
        service = mutation.timer_units()["service"]
        exec_line = next(line for line in service.splitlines() if line.startswith("ExecStart="))
        assert exec_line.split("=", 1)[1].startswith("/"), exec_line


class TestInstallTimer:
    """Writing the units where systemd will find them."""

    def test_it_writes_both_units(self, mutation: ModuleType, tmp_path: Path) -> None:
        written = mutation.install_timer(tmp_path)
        assert {p.name for p in written} == {
            "specweaver-mutation.service",
            "specweaver-mutation.timer",
        }
        assert all(p.is_file() for p in written)

    def test_installing_twice_is_idempotent(self, mutation: ModuleType, tmp_path: Path) -> None:
        """[Boundary] Re-running the installer must not drift the files it already wrote."""
        first = {p: p.read_text(encoding="utf-8") for p in mutation.install_timer(tmp_path)}
        second = {p: p.read_text(encoding="utf-8") for p in mutation.install_timer(tmp_path)}
        assert first == second

    def test_it_creates_the_directory_when_absent(
        self, mutation: ModuleType, tmp_path: Path
    ) -> None:
        target = tmp_path / "nested" / "systemd" / "user"
        assert mutation.install_timer(target)
        assert target.is_dir()

    def test_an_unwritable_target_fails_loudly(
        self, mutation: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """[Degradation] A silent install failure means a timer nobody notices is missing."""

        def _no_mkdir(*_a: object, **_k: object) -> None:
            raise OSError("read-only file system")

        monkeypatch.setattr(Path, "mkdir", _no_mkdir)
        with pytest.raises(OSError):
            mutation.install_timer(tmp_path / "nope")


class TestTheUnitCarriesAUsablePath:
    """A systemd user service inherits a minimal PATH, and `.venv/bin` is not on it.

    The unit runs `.venv/bin/python` by absolute path, so Python itself starts — which is why this
    looked fine. But the suite shells out: `tests/unit/test_architecture.py` invokes a bare `tach`,
    and the tach pytest plugin does the same at collection. Without `.venv/bin` on PATH that is a
    collection error, and a collection error makes the whole baseline red while naming no failing
    test — which is exactly the shape the nightly report showed: `green=false, failed=0`.

    Trap 2 in `docs/dev_guides/working_in_this_repo.md`, arriving by a route that guide does not
    cover: the PATH is missing from a unit file rather than from a shell.

    Proves: TECH-058 FR-2
    """

    def test_the_service_sets_a_path_including_the_venv(self) -> None:
        from _mutation_timer import timer_units

        service = timer_units()["service"]

        path_lines = [line for line in service.splitlines() if line.startswith("Environment=PATH=")]
        assert path_lines, f"no PATH is set, so the suite cannot find `tach`:\n{service}"
        assert ".venv/bin" in path_lines[0], path_lines[0]

    def test_the_path_is_absolute(self) -> None:
        """A relative entry breaks the moment a test chdirs into a temp worktree — the same trap,
        one line further down the guide."""
        from _mutation_timer import timer_units

        path_line = next(
            line
            for line in timer_units()["service"].splitlines()
            if line.startswith("Environment=PATH=")
        )
        value = path_line.removeprefix("Environment=PATH=")
        venv_entry = next(p for p in value.split(":") if ".venv/bin" in p)
        assert venv_entry.startswith("/"), venv_entry

    def test_the_system_directories_survive(self) -> None:
        """The control: prepending the venv must not drop `/usr/bin`, or `git` and `podman` vanish."""
        from _mutation_timer import timer_units

        path_line = next(
            line
            for line in timer_units()["service"].splitlines()
            if line.startswith("Environment=PATH=")
        )
        assert "/usr/bin" in path_line, path_line
