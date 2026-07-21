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

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.flow.engine.runner_utils import (
    _derive_allowed_paths,
    apply_session_policy,
)
from specweaver.core.flow.handlers.base import RunContext

_LOG = logging.getLogger("test.session_policy")


def _ctx(spec_name: str = "foo_spec.md", tmp: Path | None = None) -> RunContext:
    base = tmp or Path("/proj")
    return RunContext(project_path=base, spec_path=base / spec_name)


def _settings(
    *, session: bool = False, allowed: list[str] | None = None, min_dal: str = "DAL_B"
):
    """A minimal settings stand-in exposing `.sandbox.<knobs>` like SpecWeaverSettings."""
    sandbox = SimpleNamespace(
        enforce_session_isolation=session,
        session_allowed_paths=allowed if allowed is not None else [],
        auto_isolate_min_dal=min_dal,
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


# --------------------------------------------------------------------------- #
# T3 (INT-US-03 SF-03) — DAL-driven auto-escalation                            #
# --------------------------------------------------------------------------- #


def _git_ctx(tmp_path, spec: str = "foo_spec.md", *, git: bool = True):
    """A RunContext whose project_path is a (fake) git repo, so the Q3 git-check passes."""
    if git:
        (tmp_path / ".git").mkdir(exist_ok=True)
    return RunContext(project_path=tmp_path, spec_path=tmp_path / spec)


class TestApplySessionPolicyDalEscalation:
    """Opt-in-per-caller DAL escalation: force-off + dal_auto_escalate=True auto-enables
    session isolation when the touched code's DAL is at/above the threshold AND the project
    is a git repo (Q3 degrade otherwise)."""

    def test_escalate_dal_a_turns_session_on_with_derived_allowlist(self, tmp_path):
        # [Happy] high-assurance code (DAL_A) in a git repo auto-sandboxes; allow-list derived.
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_A
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is True
        assert ctx.allowed_paths == ["src/foo.py", "tests/test_foo.py"]

    def test_escalate_dal_b_equality_turns_on(self, tmp_path):
        # [Boundary] the threshold is inclusive: DAL_B meets a DAL_B threshold.
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_B
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is True

    def test_escalate_dal_c_below_threshold_stays_off(self, tmp_path):
        # [Boundary] DAL_C is below DAL_B -> off, allow-list empty (NFR-2).
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_C
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_escalate_dal_none_small_project_stays_off(self, tmp_path, monkeypatch):
        # [Boundary] a small project with no DAL marker resolves to None -> host mode.
        monkeypatch.setattr(
            "specweaver.core.config.dal_resolver.DALResolver.resolve",
            lambda self, target: None,
        )
        ctx = _git_ctx(tmp_path)  # dal_level defaults None
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_escalate_non_git_project_degrades_to_host(self, tmp_path):
        # [Degradation/Q3] DAL qualifies but the project is NOT a git repo -> degrade to host
        # (never hard-fail the command). Escalation stays off.
        ctx = _git_ctx(tmp_path, git=False)
        ctx.dal_level = DALLevel.DAL_A
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_no_escalate_param_leaves_high_dal_off(self, tmp_path):
        # [Boundary/CRUX] dal_auto_escalate defaults False -> sw run/sw resume are UNAFFECTED
        # even for DAL_A code (escalation is strictly caller-opt-in).
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_A
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG)  # no dal_auto_escalate
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_threshold_off_disables_escalation(self, tmp_path):
        # [Boundary] auto_isolate_min_dal="off" -> escalation disabled even for DAL_A.
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_A
        apply_session_policy(ctx, _settings(min_dal="off"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is False

    def test_force_on_wins_regardless_of_dal(self, tmp_path):
        # [Happy] explicit enforce_session_isolation=True -> on even if DAL is below threshold.
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_E
        apply_session_policy(
            ctx, _settings(session=True, min_dal="DAL_B"), _LOG, dal_auto_escalate=True
        )
        assert ctx.session_isolation is True

    def test_escalate_resolves_and_caches_dal_onto_context(self, tmp_path, monkeypatch):
        # [Happy] dal_level unset -> the policy resolves it (DAL_B) AND caches onto the context
        # so the runner does not re-resolve.
        monkeypatch.setattr(
            "specweaver.core.config.dal_resolver.DALResolver.resolve",
            lambda self, target: DALLevel.DAL_B,
        )
        ctx = _git_ctx(tmp_path)  # dal_level None
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is True
        assert ctx.dal_level == DALLevel.DAL_B

    def test_escalate_resolver_raises_degrades_off(self, tmp_path, monkeypatch):
        # [Degradation] a DAL-resolution failure must never crash the run -> best-effort off.
        def _boom(self, target):
            raise RuntimeError("dal blew up")

        monkeypatch.setattr(
            "specweaver.core.config.dal_resolver.DALResolver.resolve", _boom
        )
        ctx = _git_ctx(tmp_path)
        apply_session_policy(ctx, _settings(min_dal="DAL_B"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []

    def test_g4_raised_threshold_dal_a_excludes_dal_b(self, tmp_path):
        # [Boundary/G4] the threshold is configurable: with auto_isolate_min_dal="DAL_A",
        # a DAL_B project no longer escalates (proves it is not hard-coded to DAL_B).
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_B
        apply_session_policy(ctx, _settings(min_dal="DAL_A"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is False
        # ...but a DAL_A project does escalate under the same threshold.
        ctx2 = _git_ctx(tmp_path)
        ctx2.dal_level = DALLevel.DAL_A
        apply_session_policy(ctx2, _settings(min_dal="DAL_A"), _LOG, dal_auto_escalate=True)
        assert ctx2.session_isolation is True

    def test_g1_invalid_threshold_degrades_off(self, tmp_path):
        # [Hostile/G1] a bogus threshold reaching the helper (bypassing the settings
        # validator) must not crash — best-effort leaves the run on host.
        ctx = _git_ctx(tmp_path)
        ctx.dal_level = DALLevel.DAL_A
        apply_session_policy(ctx, _settings(min_dal="DAL_Z"), _LOG, dal_auto_escalate=True)
        assert ctx.session_isolation is False
        assert ctx.allowed_paths == []
