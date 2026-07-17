# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Direct unit tests for the INT-US-09 tri-state worktree-isolation gate resolution
(`resolve_should_isolate`). Tested directly (not transitively through the runner) so
the defensive branches stay covered even if the run loop is later refactored."""

from __future__ import annotations

from types import SimpleNamespace

from specweaver.core.flow.engine.runner import resolve_should_isolate


class TestResolveShouldIsolate:
    """Resolution: explicit per-step `use_worktree` (True/False) wins; `None` (or a
    missing attribute) defers to `context.enforce_isolation`; both reads are defensive."""

    # --- [Happy Path] None defers to the policy ---

    def test_step_none_policy_on_isolates(self) -> None:
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=None), SimpleNamespace(enforce_isolation=True)
            )
            is True
        )

    def test_step_none_policy_off_host(self) -> None:
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=None), SimpleNamespace(enforce_isolation=False)
            )
            is False
        )

    # --- [Boundary] explicit step value overrides the policy both ways ---

    def test_step_true_overrides_policy_off(self) -> None:
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=True), SimpleNamespace(enforce_isolation=False)
            )
            is True
        )

    def test_step_false_overrides_policy_on(self) -> None:
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=False), SimpleNamespace(enforce_isolation=True)
            )
            is False
        )

    # --- [Graceful Degradation / Hostile] missing attributes must never raise ---

    def test_context_missing_enforce_isolation_defaults_host(self) -> None:
        # step None + a context that lacks enforce_isolation entirely → host, no AttributeError.
        assert resolve_should_isolate(SimpleNamespace(use_worktree=None), SimpleNamespace()) is False

    def test_step_missing_use_worktree_defers_to_policy(self) -> None:
        # a step object with no use_worktree attribute → treated as None → policy decides.
        assert (
            resolve_should_isolate(SimpleNamespace(), SimpleNamespace(enforce_isolation=True)) is True
        )

    def test_both_attributes_missing_defaults_host(self) -> None:
        assert resolve_should_isolate(SimpleNamespace(), SimpleNamespace()) is False

    def test_step_true_with_context_missing_field_still_isolates(self) -> None:
        # explicit True short-circuits — the context is never read.
        assert resolve_should_isolate(SimpleNamespace(use_worktree=True), SimpleNamespace()) is True

    # --- return type is a strict bool (callers use `if should_isolate:`) ---

    def test_returns_strict_bool_true(self) -> None:
        r = resolve_should_isolate(
            SimpleNamespace(use_worktree=None), SimpleNamespace(enforce_isolation=True)
        )
        assert r is True and isinstance(r, bool)

    def test_returns_strict_bool_false(self) -> None:
        r = resolve_should_isolate(SimpleNamespace(), SimpleNamespace())
        assert r is False and isinstance(r, bool)

    # --- [Boundary] the gate keys off `is not None`, NOT truthiness ---
    # (a naive `if step_val:` rewrite would wrongly defer 0/"" to the policy)

    def test_step_zero_is_not_none_returns_false_not_policy(self) -> None:
        # 0 is not None → return bool(0)=False; must NOT fall through to enforce_isolation.
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=0), SimpleNamespace(enforce_isolation=True)
            )
            is False
        )

    def test_step_empty_string_is_not_none_returns_false_not_policy(self) -> None:
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=""), SimpleNamespace(enforce_isolation=True)
            )
            is False
        )

    def test_step_truthy_int_is_not_none_returns_true(self) -> None:
        # 1 is not None → bool(1)=True → isolate, without consulting the policy.
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=1), SimpleNamespace(enforce_isolation=False)
            )
            is True
        )

    # --- [Hostile/Wrong Input] non-bool values coerce to a STRICT bool ---

    def test_context_truthy_nonbool_coerced_true(self) -> None:
        r = resolve_should_isolate(
            SimpleNamespace(use_worktree=None), SimpleNamespace(enforce_isolation="yes")
        )
        assert r is True and isinstance(r, bool)

    def test_step_truthy_nonbool_coerced_strict_bool(self) -> None:
        r = resolve_should_isolate(SimpleNamespace(use_worktree=1), SimpleNamespace())
        assert r is True and isinstance(r, bool)

    def test_context_enforce_present_but_none_defaults_host(self) -> None:
        # attribute present but explicitly None → bool(None)=False → host.
        assert (
            resolve_should_isolate(
                SimpleNamespace(use_worktree=None), SimpleNamespace(enforce_isolation=None)
            )
            is False
        )

    # --- [Graceful Degradation] whole None objects must never raise ---

    def test_step_def_is_none_defers_to_policy(self) -> None:
        # getattr(None, "use_worktree", None) -> None -> defer to the policy.
        assert resolve_should_isolate(None, SimpleNamespace(enforce_isolation=True)) is True

    def test_context_is_none_defaults_host(self) -> None:
        assert resolve_should_isolate(SimpleNamespace(use_worktree=None), None) is False

    def test_both_none_defaults_host(self) -> None:
        assert resolve_should_isolate(None, None) is False

    def test_step_none_object_but_explicit_step_true_isolates(self) -> None:
        # context is None but the step forces isolation on → isolate, no crash.
        assert resolve_should_isolate(SimpleNamespace(use_worktree=True), None) is True
