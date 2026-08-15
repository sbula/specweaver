# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`assurance/validation`'s declared interface must be real, and must match `tach.toml`.

`context.yaml` declared `exposes: [ValidationRunner, ValidationResult, RuleSeverity]` — **three
names with zero occurrences anywhere in `src/`**. That was not a documentation wart. `tach_sync`
(`workspace/project/tach_sync.py:53-63`) **generates `tach.toml`'s `[[interfaces]]` blocks from this
field**, and tach *enforces* interfaces: running `sw`'s sync would have replaced a correct 17-name
expose list with three that do not exist, and every import from the module would have started
failing.

It also produced a real design error. `INT-US-04`'s contract and its FR-1 were written against
`ValidationResult`, a type that has never existed; the actual surface is `RuleResult` / `Finding`
(`TECH-017` recorded the symptom without finding the cause).

Two assertions, because either alone is insufficient:

* **Every declared name resolves** — otherwise the field drifts back into fiction.
* **It matches `tach.toml` exactly** — otherwise the names are real but a sync still rewrites the
  enforced interface, which is the landmine itself.

Scope is deliberate: 6 other modules have stale `exposes` (measured 2026-08-14) and are reported in
`INT-US-04_sf01_implementation_plan.md` R-1, not fixed here. Sweeping them is a different concern
from persisting validation output.

Proves: INT-US-04 FR-2.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
MODULE = "specweaver.assurance.validation"
CONTEXT = REPO_ROOT / "src" / "specweaver" / "assurance" / "validation" / "context.yaml"


def _declared_exposes() -> list[str]:
    data = yaml.safe_load(CONTEXT.read_text(encoding="utf-8"))
    return list(data.get("exposes") or [])


def _tach_exposes() -> list[str]:
    text = (REPO_ROOT / "tach.toml").read_text(encoding="utf-8")
    found = re.search(
        r'\[\[interfaces\]\]\nfrom = \[ "' + re.escape(MODULE) + r'",\]\nexpose = \[ ([^\]]*)\]',
        text,
    )
    assert found, f"no [[interfaces]] block for {MODULE} in tach.toml"
    return [n.strip().strip('"') for n in found.group(1).split(",") if n.strip()]


def _resolves(name: str) -> bool:
    """A dotted `exposes` entry is a submodule, or an attribute of one."""
    try:
        importlib.import_module(f"{MODULE}.{name}")
    except ModuleNotFoundError:
        parent, _, attr = name.rpartition(".")
        if not parent:
            return False
        try:
            return hasattr(importlib.import_module(f"{MODULE}.{parent}"), attr)
        except ModuleNotFoundError:
            return False
    return True


class TestValidationContextExposes:
    """The `exposes` field of `assurance/validation/context.yaml`."""

    def test_every_declared_name_exists(self) -> None:
        """The defect itself: three of three names were fiction."""
        missing = [name for name in _declared_exposes() if not _resolves(name)]
        assert not missing, (
            f"context.yaml declares names absent from src/: {missing}. tach_sync generates "
            f"tach.toml's enforced interface from this field, so these would break every import "
            f"from {MODULE}."
        )

    def test_it_matches_the_enforced_interface(self) -> None:
        """Real names are not enough — a sync must be a no-op, not a rewrite.

        If these two disagree, `sync_tach_toml` silently changes what tach enforces. That is the
        landmine, and it is independent of whether the declared names happen to exist.
        """
        assert sorted(_declared_exposes()) == sorted(_tach_exposes())

    def test_the_declared_list_is_not_empty(self) -> None:
        """`tach_sync` skips the interface block entirely when `exposes` is falsy.

        Emptying the field would therefore *delete* the enforced interface rather than fail — the
        quietest possible way to disable it.
        """
        assert _declared_exposes()
