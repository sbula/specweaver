# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""C-EXEC-06 SF-03 T2/T3: composition-root session-isolation policy helpers.

`_derive_allowed_paths` derives the reconcile allow-list from the spec stem (AD-2),
byte-matching `generation.py`'s target derivation. `apply_session_policy` freezes the
per-run isolation policy + allow-list onto the RunContext at the composition root, with
the NFR-2 guard: when the policy is off, `allowed_paths` MUST stay empty (the per-step
INT-US-09 path also reads it).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from types import SimpleNamespace

from specweaver.core.flow.engine.runner_utils import (
    _derive_allowed_paths,
    apply_session_policy,
)
from specweaver.core.flow.handlers.base import RunContext

_LOG = logging.getLogger("test.session_policy")


def _ctx(spec_name: str = "foo_spec.md", tmp: Path | None = None) -> RunContext:
    base = tmp or Path("/proj")
    return RunContext(project_path=base, spec_path=base / spec_name)


def _settings(*, session: bool = False, allowed: list[str] | None = None):
    """A minimal settings stand-in exposing `.sandbox.<knobs>` like SpecWeaverSettings."""
    sandbox = SimpleNamespace(
        enforce_session_isolation=session,
        session_allowed_paths=allowed if allowed is not None else [],
    )
    return SimpleNamespace(sandbox=sandbox)


# --------------------------------------------------------------------------- #
# T2 — _derive_allowed_paths                                                   #
# --------------------------------------------------------------------------- #


class TestDeriveAllowedPaths:
    def test_happy_strips_spec_suffix(self):
        # [Happy] foo_spec -> src/foo.py + tests/test_foo.py
        assert _derive_allowed_paths(Path("/p/foo_spec.md")) == [
            "src/foo.py",
            "tests/test_foo.py",
        ]

    def test_c1_matches_generation_replace_quirk_not_removesuffix(self):
        # [Boundary/C1] generation.py uses .replace("_spec","") (removes EVERY "_spec"
        # substring, including inside "_special"), NOT .removesuffix. The allow-list MUST
        # match the path the handler actually generates, else the real file is stripped.
        # "my_special_spec" -> .replace -> "myial" (NOT "my_special").
        assert _derive_allowed_paths(Path("/p/my_special_spec.md")) == [
            "src/myial.py",
            "tests/test_myial.py",
        ]

    def test_boundary_stem_without_spec_suffix(self):
        assert _derive_allowed_paths(Path("/p/foo.md")) == [
            "src/foo.py",
            "tests/test_foo.py",
        ]

    def test_hostile_degenerate_dotfile_stem_is_safe(self):
        # [Hostile] a dotfile spec (".md") has stem ".md" in pathlib (no suffix split), so
        # the derived paths are degenerate ("src/.md.py") but SAFE — they match no real
        # generated file, so nothing extra is ever authorized for write-back.
        assert _derive_allowed_paths(Path("/p/.md")) == ["src/.md.py", "tests/test_.md.py"]

    def test_boundary_forward_slash_on_all_platforms(self):
        # [Boundary] strip_merge compares git --name-only output (forward slashes even on
        # Windows). The derived paths MUST use "/" literally, never os.sep.
        for p in _derive_allowed_paths(Path("/p/bar_spec.md")):
            assert "/" in p
            if os.sep != "/":
                assert os.sep not in p


# --------------------------------------------------------------------------- #
# T3 — apply_session_policy                                                    #
# --------------------------------------------------------------------------- #


class TestApplySessionPolicy:
    def test_happy_on_empty_override_derives(self):
        # [Happy] policy on + empty override -> session on + derived allow-list.
        ctx = _ctx("foo_spec.md")
        apply_session_policy(ctx, _settings(session=True), _LOG)
        assert ctx.session_isolation is True
        assert ctx.allowed_paths == ["src/foo.py", "tests/test_foo.py"]

    def test_happy_override_used_verbatim(self):
        # [Happy] non-empty override -> used verbatim (derivation NOT applied).
        ctx = _ctx("foo_spec.md")
        override = ["src/custom.py", "lib/helper.py"]
        apply_session_policy(ctx, _settings(session=True, allowed=override), _LOG)
        assert ctx.session_isolation is True
        assert ctx.allowed_paths == override

    def test_nfr2_off_leaves_allowed_paths_empty(self):
        # [Boundary/NFR-2] policy OFF -> session off AND allowed_paths stays [] so the
        # per-step INT-US-09 strip_merge behavior is unchanged.
        ctx = _ctx("foo_spec.md")
        apply_session_policy(ctx, _settings(session=False), _LOG)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_nfr2_off_does_not_populate_even_with_override_present(self):
        # [Boundary/NFR-2] even if an override is configured, an OFF policy must not leak
        # it onto the context (would change the per-step path).
        ctx = _ctx("foo_spec.md")
        apply_session_policy(ctx, _settings(session=False, allowed=["src/x.py"]), _LOG)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_c3_junk_override_is_fail_closed(self):
        # [Hostile/C3] a non-empty junk override ([""]) is used verbatim -> matches no real
        # file -> everything stripped (fail-closed, never fail-open).
        ctx = _ctx("foo_spec.md")
        apply_session_policy(ctx, _settings(session=True, allowed=[""]), _LOG)
        assert ctx.session_isolation is True
        assert ctx.allowed_paths == [""]

    def test_c2_derivation_failure_leaves_context_default(self, monkeypatch):
        # [Degradation/C2] if the derivation raises, the context must be left FULLY default
        # (session off, allow-list empty) — never a half-applied "session on, empty list"
        # state that would silently drop all generated code. No exception escapes.
        def _boom(_spec):
            raise RuntimeError("derivation blew up")

        monkeypatch.setattr(
            "specweaver.core.flow.engine.runner_utils._derive_allowed_paths", _boom
        )
        ctx = _ctx("foo_spec.md")
        apply_session_policy(ctx, _settings(session=True), _LOG)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_degradation_missing_sandbox_defaults_off(self):
        # [Degradation] a settings object without `.sandbox` -> policy off, no crash.
        ctx = _ctx("foo_spec.md")
        apply_session_policy(ctx, SimpleNamespace(), _LOG)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_boundary_both_knobs_on_sets_session(self):
        # [Boundary] per-run + per-step both on -> session_isolation True (execute_run
        # suppresses per-step nesting at runtime; that precedence is not this helper's job).
        ctx = _ctx("foo_spec.md")
        settings = _settings(session=True)
        settings.sandbox.enforce_worktree_isolation = True
        apply_session_policy(ctx, settings, _LOG)
        assert ctx.session_isolation is True
