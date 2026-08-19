# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Whether a step runs isolated, and under what allow-list.

The policy questions — tri-state worktree gating, DAL escalation, and the reconcile allow-list
derived from the spec stem — are one contract, and a module named for it can be contradicted by the
next addition. A grab-bag named for being leftovers cannot.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def resolve_should_isolate(step_def: Any, context: Any) -> bool:
    """Tri-state worktree-isolation gate resolution.

    An explicit per-step ``use_worktree`` (``True``/``False``) wins; ``None`` — or a
    missing attribute — defers to the US-9 isolation policy (``context.isolation.enforce_isolation``,
    resolved at the composition root). Both reads are defensive (``getattr`` with a default)
    so a partially-populated step or context never crashes the runner, and the result is a
    strict ``bool``.
    """
    step_val = getattr(step_def, "use_worktree", None)
    if step_val is not None:
        return bool(step_val)
    # Two hops, both guarded: callers do pass `None` for the context.
    return bool(getattr(getattr(context, "isolation", None), "enforce_isolation", False))


def _derive_allowed_paths(spec_path: Path) -> list[str]:
    """The reconcile allow-list, derived from the spec stem.

    Mirrors the pipeline's generation targets so the single end-of-run strip-merge
    authorizes exactly the files the run actually generates. Inside a session,
    ``execute_run`` nulls ``output_dir``, so the generation handlers fall back to their
    defaults (``src/<stem>.py`` / ``tests/test_<stem>.py``) — hence the ``src/``/``tests/``
    prefixes here, not the composition-root ``output_dir``.

    The stem transform MUST stay byte-identical to the generation handlers
    (``generation.py``: ``spec_path.stem.replace("_spec", "")`` — note ``.replace``, NOT
    ``.removesuffix``: it removes every ``_spec`` substring). If it drifts, the derived
    allow-list stops matching the generated path and the real file gets stripped.

    Paths are repo-relative with forward slashes (git ``--name-only`` form on every
    platform, including Windows) — never ``os.sep``.
    """
    stem = spec_path.stem.replace("_spec", "")
    return [f"src/{stem}.py", f"tests/test_{stem}.py"]


def apply_isolation_policy(
    context: RunContext,
    settings: Any,
    logger: logging.Logger,
) -> None:
    """Freeze BOTH worktree-isolation policies onto the context, from resolved settings.

    Per-step (`enforce_isolation`) and per-run (`session_isolation` + `allowed_paths`). This is the
    composition-root decision `ADR-002` places at the edge, and it lives here rather than beside one
    edge because there are two: `sw run`/`sw resume` and the API's run endpoints. It used to live in
    the CLI module alone, so an API-triggered run executed with isolation off whatever `[sandbox]`
    declared.

    Takes RESOLVED settings rather than a database, because the two roots resolve differently — the
    CLI synchronously, the API with `load_settings_async` — and calling the sync loader inside an
    async endpoint would block the event loop to share code that is not the part worth sharing.

    Also freezes the autonomy policy — the execution-mode dial — because it is the same kind of
    decision with the same two roots: seeding it at one of them would leave runs from the other
    resolving against no policy at all.

    Deliberately does NOT populate `context.model.config`: that would also expose
    `[sandbox] execution_mode` and incidentally activate container QA on this path.

    **Best-effort by contract:** a settings-resolution failure must never crash a run, so the
    policies fall back to their defaults (off).
    """
    try:
        context.isolation = context.isolation.model_copy(
            update={
                "enforce_isolation": settings.sandbox.enforce_worktree_isolation,
                # Defensive: a settings object without this attribute must still get its
                # isolation policy. Reading it strictly would drop BOTH on the floor, because
                # the whole block is best-effort.
                "autonomy": getattr(settings, "autonomy", None),
            }
        )
        apply_session_policy(context, settings, logger)
    except Exception:  # best-effort here — never crash a run over policy resolution
        logger.debug("Could not apply worktree isolation policy; defaults (off) will be used.")


def apply_session_policy(
    context: RunContext,
    settings: Any,
    logger: logging.Logger,
    *,
    dal_auto_escalate: bool = False,
) -> None:
    """Freeze per-run isolation policy onto the context.

    Called at the composition root (`ADR-002`). Reads the opt-in ``[sandbox]`` knobs and,
    **only when per-run isolation is on**, populates ``allowed_paths`` (the configured
    override, else the derived generation targets).

    ``dal_auto_escalate``: when True and the explicit
    ``enforce_session_isolation`` flag is off, the policy auto-enables session isolation if
    the touched code's resolved DAL is at/above the ``auto_isolate_min_dal`` threshold
    (default ``DAL_B``). This is **opt-in per caller** — ``sw implement`` passes True;
    ``sw run``/``sw resume`` leave it False, so their behavior is byte-identical (escalation
    never even resolves a DAL for them).

    When the policy is OFF, ``allowed_paths`` is left EMPTY — the per-step path
    (``execute_in_sandbox``) also reads ``allowed_paths``, so populating it here would silently
    change per-step ``strip_merge`` behavior.

    No half-apply: the allow-list is computed BEFORE either field is mutated, so a
    derivation failure leaves the context fully default (session off) rather than the
    dangerous "session on, empty allow-list" state that would drop all generated code.
    Both fields land in ONE ``model_copy``, so the half-applied state cannot be represented.
    Splitting it in two brings the danger back.
    Best-effort: never raises (the composition root also wraps this call defensively).
    """
    try:
        sandbox = getattr(settings, "sandbox", None)
        session_on = bool(getattr(sandbox, "enforce_session_isolation", False))
        if not session_on and dal_auto_escalate:
            session_on = _dal_requires_isolation(context, sandbox, logger)
        if not session_on:
            context.isolation = context.isolation.model_copy(update={"session_isolation": False})
            return
        override = list(getattr(sandbox, "session_allowed_paths", None) or [])
        allowed = override or _derive_allowed_paths(context.spec_path)
        context.isolation = context.isolation.model_copy(
            update={"session_isolation": True, "allowed_paths": allowed}
        )
    except Exception:  # best-effort — a policy-resolution failure must never crash a run
        logger.debug(
            "Could not apply per-run session-isolation policy; leaving it off.",
            exc_info=True,
        )


def seed_dal_level(context: RunContext) -> Any:
    """Resolve the run's DAL onto ``context.isolation``, caching it, and return it.

    Target is ``spec_path`` when it exists, else ``project_path``. Idempotent, so the second
    caller never re-resolves.
    """
    if context.isolation.dal_level is not None:
        return context.isolation.dal_level

    from specweaver.core.config.dal_resolver import DALResolver

    target = context.spec_path if context.spec_path.exists() else context.project_path
    dal = DALResolver(context.project_path).resolve(target)
    context.isolation = context.isolation.model_copy(update={"dal_level": dal})
    return dal


def _dal_requires_isolation(context: RunContext, sandbox: Any, logger: logging.Logger) -> bool:
    """Does the touched code's DAL meet the escalation threshold?

    Reads ``auto_isolate_min_dal`` (a ``DALLevel`` name, or ``"off"`` to disable), then defers
    to ``seed_dal_level`` for the run's DAL (resolving and caching it if the runner has not
    already). Returns True iff the resolved DAL is at or above the threshold in strictness.
    Any failure ⇒ False (the caller stays on host).
    """
    from specweaver.commons.enums.dal import DALLevel

    threshold_raw = getattr(sandbox, "auto_isolate_min_dal", "DAL_B")
    if not threshold_raw or str(threshold_raw).lower() == "off":
        return False
    threshold = DALLevel(threshold_raw)

    dal = seed_dal_level(context)
    if dal is None or dal.rank < threshold.rank:
        return False

    # Q3: auto-escalation must NEVER break the command. If the project cannot host a git
    # worktree (not a git repo), degrade to host mode with a warning instead of failing.
    # (An explicit ``enforce_session_isolation`` still fails-closed at ``execute_run``.)
    if not (context.project_path / ".git").exists():
        logger.warning(
            "DAL %s meets the auto-isolation threshold %s but %s is not a git repository; "
            "running the loop on host (unsandboxed). `git init` to enable worktree isolation.",
            dal.value,
            threshold.value,
            context.project_path,
        )
        return False
    return True
