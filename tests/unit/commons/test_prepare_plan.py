# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the prepare phase will do with a project, before it does it.

`TECH-031`'s last candidate approach: check the layout at configuration time rather than at the
moment a QA run fails inside a container. The three rungs before it each added behaviour a reader
would otherwise meet by surprise — a fresh resolution that does not reproduce their pins, tox lines
skipped, a runner the sandbox chose — so the value is no longer only "you are unsupported", it is
"here is what will happen and what it will cost".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.commons.prepare_plan import plan_for

if TYPE_CHECKING:
    from pathlib import Path

_MANIFEST = '[project]\nname = "t"\nversion = "0"\ndependencies = []\n'


def _project(tmp_path: Path, **files: str) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    for name, text in files.items():
        (root / name.replace("__", ".")).write_text(text, encoding="utf-8")
    return root


class TestPlanFor:
    """One decision, read before it is acted on."""

    def test_a_locked_project_with_its_own_runner_needs_no_warning(self, tmp_path: Path) -> None:
        root = _project(
            tmp_path,
            pyproject__toml=_MANIFEST.rstrip() + '\n\n[dependency-groups]\ntests = ["pytest"]\n',
            uv__lock="locked",
        )

        plan = plan_for(root)

        assert plan.route == "locked"
        assert plan.runner_source == "pyproject.toml"
        assert plan.groups == ("tests",)
        assert plan.warnings == (), plan.warnings

    def test_a_missing_lockfile_is_reported_as_a_loss_of_reproducibility(
        self, tmp_path: Path
    ) -> None:
        """The cost of rung 1, stated where someone can act on it — commit a lockfile."""
        root = _project(
            tmp_path,
            pyproject__toml=_MANIFEST.rstrip() + '\n\n[dependency-groups]\ntests = ["pytest"]\n',
        )

        plan = plan_for(root)

        assert plan.route == "resolved"
        assert any("uv.lock" in w and "reproduce" in w for w in plan.warnings), plan.warnings

    def test_a_tox_declaration_is_named_with_what_it_could_not_read(self, tmp_path: Path) -> None:
        root = _project(
            tmp_path,
            uv__lock="locked",
            pyproject__toml=_MANIFEST,
            tox__ini="[testenv]\ndeps =\n    pytest\n    py3{10-14}: -r extra.pip\n",
        )

        plan = plan_for(root)

        assert plan.runner_source == "tox.ini"
        assert plan.skipped == ("py3{10-14}: -r extra.pip",)
        assert any("substitution" in w for w in plan.warnings), plan.warnings

    def test_a_project_declaring_nothing_is_told_a_runner_will_be_supplied(
        self, tmp_path: Path
    ) -> None:
        root = _project(tmp_path, uv__lock="locked", pyproject__toml=_MANIFEST)

        plan = plan_for(root)

        assert plan.runner_source == "sandbox"
        assert any("not the project's choice" in w for w in plan.warnings), plan.warnings

    def test_a_tree_with_no_manifest_can_be_prepared_at_all(self, tmp_path: Path) -> None:
        """22 of the 150 corpus repositories: `pyproject.toml` under a monorepo path, or `setup.py`.

        There is nothing for `uv` to read, so no environment is built and the QA run falls through
        to the image's interpreter. Saying so at configuration time is the whole point of this
        command — that failure is otherwise met inside a container, minutes later.
        """
        root = _project(tmp_path, README__md="nothing here\n")

        plan = plan_for(root)

        assert plan.route == "none"
        assert plan.runner_source == ""
        assert any("no environment can be built" in w for w in plan.warnings), plan.warnings
