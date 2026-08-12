# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""CLI spec resolution + validation-battery selection (INT-US-21 SF-03 CB-1, FR-8).

Two seams, both integration by nature:

* **Argument -> file.** `resolve_spec_path` turns a CLI argument into a path on disk. A unit test
  on a pure function would not notice a wrong `specs/` root or a suffix that drifts from the one
  `DraftFeatureHandler` enforces, because both only manifest against a real filesystem.
* **`kind` -> battery.** The bundled `feature_decomposition.yaml` sets `params: kind: feature`, and
  `ValidateSpecHandler` selects `validation_spec_feature` from it. **Nothing proved that before
  this file.** The handler-reachability test proves `validate+feature` *resolves to a handler*; it
  says nothing about which of the two batteries then runs. A silent fallback to
  `validation_spec_default` would leave every downstream assertion in the SF-03 e2e green while the
  wrong rule set executed — the battery differs by exactly one rule (`s04_dependency_dir`), so the
  failure would be quiet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.core.flow.engine.models import PipelineStep
from specweaver.core.flow.handlers.draft import FEATURE_SPEC_SUFFIX
from specweaver.core.flow.interfaces.spec_path_resolution import (
    derive_feature_spec_path,
    resolve_spec_path,
)


def _make(project: Path, relative: str) -> Path:
    target = project / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# spec\n", encoding="utf-8")
    return target


class TestFeatureDecompositionResolution:
    """FR-8: `sw run feature_decomposition <name>` must find the feature spec."""

    def test_bare_name_resolves_to_the_feature_spec(self, tmp_path: Path) -> None:
        expected = _make(tmp_path, f"specs/onboarding{FEATURE_SPEC_SUFFIX}")

        resolved = resolve_spec_path("feature_decomposition", "onboarding", tmp_path)

        assert resolved == expected

    def test_the_suffix_is_defined_in_exactly_one_place(self) -> None:
        """R-2: the resolver must IMPORT the suffix, never re-spell it.

        The obvious version of this test — asserting the resolved name ends with
        ``FEATURE_SPEC_SUFFIX`` — cannot detect the defect it names, because the test builds its
        expectation from the same constant. A source that hardcoded the identical literal would
        pass it. So assert the property that actually matters: one definition, repo-wide.
        """
        import inspect

        from specweaver.core.flow.handlers import draft
        from specweaver.core.flow.interfaces import spec_path_resolution

        assert inspect.getsource(draft).count('FEATURE_SPEC_SUFFIX = "') == 1
        assert '_feature_spec.md"' not in inspect.getsource(spec_path_resolution).replace(
            "FEATURE_SPEC_SUFFIX", ""
        ), "the resolver re-spells the suffix instead of importing it"

    def test_explicit_path_still_wins_over_derivation(self, tmp_path: Path) -> None:
        """R-1: an existing path is returned before any pipeline-specific branch runs."""
        explicit = _make(tmp_path, "elsewhere/custom_feature_spec.md")

        resolved = resolve_spec_path("feature_decomposition", str(explicit), tmp_path)

        assert resolved == explicit

    def test_missing_bare_name_still_derives_a_path_for_a_clear_downstream_error(
        self, tmp_path: Path
    ) -> None:
        """Resolution does not assert existence — the handler reports the missing file."""
        resolved = resolve_spec_path("feature_decomposition", "absent", tmp_path)

        assert resolved == tmp_path / "specs" / f"absent{FEATURE_SPEC_SUFFIX}"
        assert not resolved.exists()

    def test_a_name_already_carrying_the_suffix_is_not_doubled(self, tmp_path: Path) -> None:
        """`onboarding_feature_spec.md` as a bare name must not become `..._feature_spec_feature_spec.md`."""
        expected = _make(tmp_path, f"specs/onboarding{FEATURE_SPEC_SUFFIX}")

        resolved = resolve_spec_path(
            "feature_decomposition", f"onboarding{FEATURE_SPEC_SUFFIX}", tmp_path
        )

        assert resolved == expected


class TestOtherPipelinesAreUnaffected:
    """NFR-1: the delivered `new_feature` journey must not change."""

    def test_new_feature_still_derives_the_plain_spec_suffix(self, tmp_path: Path) -> None:
        resolved = resolve_spec_path("new_feature", "greeter", tmp_path)

        assert resolved == tmp_path / "specs" / "greeter_spec.md"
        assert not resolved.name.endswith(FEATURE_SPEC_SUFFIX)

    def test_validate_only_treats_the_argument_as_a_path(self, tmp_path: Path) -> None:
        spec = _make(tmp_path, "specs/calculator.md")

        resolved = resolve_spec_path("validate_only", str(spec), tmp_path)

        assert resolved == spec

    def test_unknown_pipeline_falls_back_to_the_literal_argument(self, tmp_path: Path) -> None:
        resolved = resolve_spec_path("some_other_pipeline", "nope", tmp_path)

        assert resolved == Path("nope")


class TestHostileArguments:
    """A bare name becomes a path segment — it must not escape `specs/`."""

    @pytest.mark.parametrize("hostile", ["../../etc/passwd", "..", "a/b", "", "."])
    def test_traversal_in_a_bare_name_cannot_escape_the_specs_directory(
        self, hostile: str, tmp_path: Path
    ) -> None:
        """No `or not is_absolute()` escape hatch.

        The first version of this assertion carried one, which meant ANY relative result passed
        without being inspected — it is how the test passed before the guard even existed. The
        contract is stated positively instead: whatever comes back must not, once resolved, sit
        outside the project.
        """
        assert derive_feature_spec_path(hostile, tmp_path) is None, (
            f"{hostile!r} produced a derived path; a bare name becomes a path segment"
        )

        resolved = resolve_spec_path("feature_decomposition", hostile, tmp_path)

        # Falling through to the literal argument is the documented behaviour for every
        # pipeline ("will fail later with clear message"), so the claim is narrower than
        # "stays inside the project": nothing may be DERIVED outside specs/.
        if str(resolved).endswith(FEATURE_SPEC_SUFFIX):
            landed = resolved if resolved.is_absolute() else (tmp_path / resolved)
            assert landed.resolve().is_relative_to((tmp_path / "specs").resolve()), (
                f"{hostile!r} derived {resolved}, outside specs/"
            )


class TestKindParamSelectsTheFeatureBattery:
    """The `kind` -> battery seam.

    The first version of this class compared the two battery YAMLs and read the bundled pipeline's
    params. Neither touches `ValidateSpecHandler`, which is what actually performs the selection —
    so the class asserted less than its own name claimed (vacuous-proof pattern 6). It now drives
    the handler and counts the rules that really executed: the feature battery is the default minus
    `S04`, so the two are distinguishable by behaviour alone.
    """

    SPEC = """# Onboarding Feature Spec

## 1. Purpose

Registers a customer.

## Done Definition

- [ ] registers a customer (FR-1)
"""

    def _spec(self, tmp_path: Path) -> Path:
        spec = tmp_path / "onboarding_feature_spec.md"
        spec.write_text(self.SPEC, encoding="utf-8")
        return spec

    async def _rules_for(self, tmp_path: Path, **params: str) -> list[str]:
        from specweaver.core.flow.engine.models import StepAction, StepTarget
        from specweaver.core.flow.handlers.run_context import RunContext
        from specweaver.core.flow.handlers.validation import ValidateSpecHandler

        step = PipelineStep(
            name="validate", action=StepAction.VALIDATE, target=StepTarget.SPEC, params=params
        )
        ctx = RunContext(project_path=tmp_path, spec_path=self._spec(tmp_path))
        result = await ValidateSpecHandler().execute(step, ctx)
        return [r["rule_id"] for r in result.output["results"]]

    @pytest.mark.asyncio()
    async def test_kind_feature_runs_the_feature_battery(self, tmp_path: Path) -> None:
        rules = await self._rules_for(tmp_path, kind="feature")

        assert "S04" not in rules, "kind=feature silently fell back to the default battery"
        assert len(rules) == 11

    @pytest.mark.asyncio()
    async def test_no_kind_runs_the_default_battery(self, tmp_path: Path) -> None:
        """The control. Without it, an 11-rule assertion proves nothing about *selection*."""
        rules = await self._rules_for(tmp_path)

        assert "S04" in rules
        assert len(rules) == 12

    def test_the_bundled_pipeline_still_declares_the_kind_param(self) -> None:
        """The selection above is driven by this YAML param; losing it is a silent downgrade."""
        from ruamel.yaml import YAML

        pipelines = (
            Path(__file__).resolve().parents[4] / "src" / "specweaver" / "workflows" / "pipelines"
        )
        data = YAML(typ="safe").load(
            (pipelines / "feature_decomposition.yaml").read_text(encoding="utf-8")
        )
        step = next(s for s in data["steps"] if s["name"] == "validate_feature")

        assert step["params"]["kind"] == "feature"
