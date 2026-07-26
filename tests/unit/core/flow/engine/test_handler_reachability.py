# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Handler reachability — every declared step combination resolves to a live handler.

The defect this pins (INT-US-21 §Research, gap 1): `D-INTL-02` added
``(DRAFT, FEATURE)`` and ``(VALIDATE, FEATURE)`` to ``VALID_STEP_COMBINATIONS`` and shipped a
``feature_decomposition.yaml`` declaring both steps — but never added the
``StepHandlerRegistry`` rows. The shipped pipeline could not execute a single step, and nothing
failed for months because every test drove ``DecomposeFeatureHandler`` directly instead of
driving the YAML that ships to users.

Two invariants, weakest link first:

1. ``VALID_STEP_COMBINATIONS`` == the set of registered combinations. This catches the defect at
   the moment a combination is *declared*, before any pipeline ships it. It is the check that
   would have failed `D-INTL-02` on its own commit.
2. Every step of every bundled pipeline resolves to a registered handler. This catches the
   opposite direction: a pipeline shipping a combination nobody declared.

``scripts/check_story_preconditions.py`` already runs invariant 2, but only at the *consuming*
story's Phase 0 — too late, because the debt has already shipped and sat. These run in every
suite run, so the *producing* story cannot commit without them.

Helpers are module-level and tested directly against deliberately broken inputs (rather than
trusting the real-data assertions to exercise their branches), because a guard test that cannot
fail is worse than no guard test at all.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from specweaver.core.flow.engine.models import (
    VALID_STEP_COMBINATIONS,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

PIPELINES_DIR = (
    Path(__file__).resolve().parents[5] / "src" / "specweaver" / "workflows" / "pipelines"
)

#: Bundled YAML files under pipelines/ that are not pipelines at all.
NON_PIPELINE_FILES = {"context.yaml"}


# ---------------------------------------------------------------------------
# Helpers (tested directly below)
# ---------------------------------------------------------------------------


def registered_combinations(
    registry: StepHandlerRegistry,
) -> set[tuple[StepAction, StepTarget]]:
    """Every (action, target) the registry resolves, probed through the public API only."""
    return {
        (action, target)
        for action in StepAction
        for target in StepTarget
        if registry.get(action, target) is not None
    }


def flow_steps(data: Any) -> list[tuple[str, Any, Any]]:
    """Return ``(step_name, action, target)`` for every step declaring a flow ``action``.

    Validation batteries live in the same directory and declare ``rule:`` instead of
    ``action:``/``target:`` — they yield nothing here. Malformed shapes (non-dict payload,
    ``steps`` not a list, a step that is not a mapping) yield nothing rather than raising, so a
    single bad file cannot mask the rest of the sweep; a step that declares ``action`` but no
    ``target`` IS returned, with ``target=None``, so it surfaces as unresolvable.
    """
    if not isinstance(data, dict):
        return []
    steps = data.get("steps")
    if not isinstance(steps, list):
        return []
    out: list[tuple[str, Any, Any]] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or "action" not in step:
            continue
        name = step.get("name")
        label = name if isinstance(name, str) and name else f"<step {index}>"
        out.append((label, step.get("action"), step.get("target")))
    return out


def unresolvable_steps(
    registry: StepHandlerRegistry,
    steps: list[tuple[str, str, Any, Any]],
) -> list[str]:
    """Which ``(file, step, action, target)`` entries have no registered handler."""
    bad: list[str] = []
    for filename, step_name, action, target in steps:
        try:
            resolved = registry.get(StepAction(action), StepTarget(target))
        except ValueError:
            bad.append(f"{filename}::{step_name} declares unknown action/target {action!r}/{target!r}")
            continue
        if resolved is None:
            bad.append(f"{filename}::{step_name} ({action}+{target}) has no registered handler")
    return bad


def discover_flow_steps(pipelines_dir: Path) -> tuple[list[tuple[str, str, Any, Any]], list[Path]]:
    """Sweep the bundled pipelines recursively.

    Returns the flat list of ``(filename, step, action, target)`` and the battery files that
    declared no flow action, so both halves can be asserted non-empty.
    """
    yaml = YAML(typ="safe")
    found: list[tuple[str, str, Any, Any]] = []
    batteries: list[Path] = []
    for path in sorted(pipelines_dir.rglob("*.yaml")):
        if path.name in NON_PIPELINE_FILES:
            continue
        data = yaml.load(path)
        steps = flow_steps(data)
        if not steps:
            batteries.append(path)
            continue
        found.extend((path.name, name, action, target) for name, action, target in steps)
    return found, batteries


class _PartialRegistry(StepHandlerRegistry):
    """A registry with specific rows removed, to prove the detectors can fail."""

    def __init__(self, drop: set[tuple[StepAction, StepTarget]]) -> None:
        super().__init__()
        for key in drop:
            self._handlers.pop(key, None)


# ---------------------------------------------------------------------------
# Invariant 1 — declaration and registration cannot diverge
# ---------------------------------------------------------------------------


class TestDeclaredCombinationsAreRegistered:
    """VALID_STEP_COMBINATIONS and the registry must be the same set."""

    def test_every_valid_combination_has_a_handler(self) -> None:
        missing = VALID_STEP_COMBINATIONS - registered_combinations(StepHandlerRegistry())
        assert not missing, (
            "These (action, target) pairs are declared valid but no handler is registered, so any "
            "pipeline using them dies at runtime with 'No handler registered':\n  "
            + "\n  ".join(f"{a}+{t}" for a, t in sorted(missing))
        )

    def test_no_handler_outside_the_declared_set(self) -> None:
        orphans = registered_combinations(StepHandlerRegistry()) - VALID_STEP_COMBINATIONS
        assert not orphans, (
            "These handlers are registered but the combination is not in "
            "VALID_STEP_COMBINATIONS, so PipelineDefinition.validate_flow() rejects any pipeline "
            "that uses them:\n  " + "\n  ".join(f"{a}+{t}" for a, t in sorted(orphans))
        )

    def test_declared_set_is_not_empty(self) -> None:
        """Guards the two assertions above against a vacuous empty-set pass."""
        assert len(VALID_STEP_COMBINATIONS) >= 20
        assert len(registered_combinations(StepHandlerRegistry())) >= 20


# ---------------------------------------------------------------------------
# Invariant 2 — every bundled pipeline is executable
# ---------------------------------------------------------------------------


class TestBundledPipelinesResolve:
    """Every step of every shipped pipeline resolves to a real handler."""

    def test_every_bundled_step_resolves(self) -> None:
        steps, _ = discover_flow_steps(PIPELINES_DIR)
        problems = unresolvable_steps(StepHandlerRegistry(), steps)
        assert not problems, "Bundled pipelines that cannot run:\n  " + "\n  ".join(problems)

    def test_sweep_is_not_vacuous(self) -> None:
        """A wrong PIPELINES_DIR silently finding nothing is how two tests skipped for months."""
        assert PIPELINES_DIR.is_dir(), f"pipelines dir not found: {PIPELINES_DIR}"
        steps, batteries = discover_flow_steps(PIPELINES_DIR)
        files = {filename for filename, *_ in steps}
        assert len(files) >= 5, f"expected >=5 flow pipelines, found {sorted(files)}"
        assert len(steps) >= 15, f"expected >=15 flow steps, found {len(steps)}"
        assert batteries, "expected at least one validation battery to exercise the skip branch"

    def test_frameworks_subdirectory_is_swept(self) -> None:
        """rglob, not glob: the framework overlays are a directory deeper."""
        _, batteries = discover_flow_steps(PIPELINES_DIR)
        assert any(
            p.parent.name == "java" for p in batteries
        ), "frameworks/java/*.yaml was not reached — discovery is not recursive"


# ---------------------------------------------------------------------------
# Detector tests — prove the guards above can actually fail
# ---------------------------------------------------------------------------


class TestDetectorsCanFail:
    """Graceful degradation: the detectors must report, not silently pass."""

    def test_missing_handler_is_reported(self) -> None:
        dropped = (StepAction.DECOMPOSE, StepTarget.FEATURE)
        registry = _PartialRegistry({dropped})
        problems = unresolvable_steps(
            registry, [("feature_decomposition.yaml", "decompose", "decompose", "feature")]
        )
        assert len(problems) == 1
        assert "no registered handler" in problems[0]

    def test_partial_registry_breaks_invariant_one(self) -> None:
        """The set-equality invariant is sensitive to a single dropped row."""
        registry = _PartialRegistry({(StepAction.DRAFT, StepTarget.FEATURE)})
        assert VALID_STEP_COMBINATIONS - registered_combinations(registry) == {
            (StepAction.DRAFT, StepTarget.FEATURE)
        }

    def test_step_without_target_is_reported(self) -> None:
        problems = unresolvable_steps(
            StepHandlerRegistry(), [("broken.yaml", "s", "decompose", None)]
        )
        assert len(problems) == 1
        assert "unknown action/target" in problems[0]

    def test_unknown_action_is_reported(self) -> None:
        problems = unresolvable_steps(
            StepHandlerRegistry(), [("broken.yaml", "s", "teleport", "feature")]
        )
        assert len(problems) == 1
        assert "unknown action/target" in problems[0]

    def test_healthy_input_reports_nothing(self) -> None:
        problems = unresolvable_steps(
            StepHandlerRegistry(), [("ok.yaml", "decompose", "decompose", "feature")]
        )
        assert problems == []


# ---------------------------------------------------------------------------
# flow_steps — boundary and hostile input
# ---------------------------------------------------------------------------


class TestFlowStepsParsing:
    """Boundary + hostile shapes must degrade to [] rather than raise."""

    def test_battery_step_shape_is_excluded(self) -> None:
        """Validation batteries declare `rule:`, not `action:`/`target:`."""
        data = {"name": "validation_spec_default", "steps": [{"name": "s01", "rule": "S01"}]}
        assert flow_steps(data) == []

    def test_flow_step_shape_is_extracted(self) -> None:
        data = {"steps": [{"name": "decompose", "action": "decompose", "target": "feature"}]}
        assert flow_steps(data) == [("decompose", "decompose", "feature")]

    def test_action_without_target_is_kept_for_reporting(self) -> None:
        assert flow_steps({"steps": [{"name": "s", "action": "draft"}]}) == [("s", "draft", None)]

    def test_unnamed_step_gets_positional_label(self) -> None:
        assert flow_steps({"steps": [{"action": "draft", "target": "spec"}]}) == [
            ("<step 0>", "draft", "spec")
        ]

    def test_extends_only_battery_has_no_steps_key(self) -> None:
        assert flow_steps({"name": "validation_spec_feature", "extends": "x", "remove": ["y"]}) == []

    def test_none_payload(self) -> None:
        assert flow_steps(None) == []

    def test_non_dict_payload(self) -> None:
        assert flow_steps(["not", "a", "mapping"]) == []
        assert flow_steps("a string") == []

    def test_steps_not_a_list(self) -> None:
        assert flow_steps({"steps": {"action": "draft"}}) == []
        assert flow_steps({"steps": None}) == []

    def test_non_mapping_step_entries_are_skipped(self) -> None:
        data = {"steps": ["oops", None, 42, {"action": "draft", "target": "spec", "name": "ok"}]}
        assert flow_steps(data) == [("ok", "draft", "spec")]

    def test_empty_step_name_falls_back_to_position(self) -> None:
        assert flow_steps({"steps": [{"name": "", "action": "draft", "target": "spec"}]}) == [
            ("<step 0>", "draft", "spec")
        ]
