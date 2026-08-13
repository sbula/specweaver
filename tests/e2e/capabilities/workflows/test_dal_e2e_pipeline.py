# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""End-to-end proof that a nested DAL boundary changes how `sw check` judges a spec.

`TECH-017`. Both tests in this file previously asserted `exit_code in (0, 1)` — which accepts a
pass and a failure alike — and neither could have failed for the reason its docstring named. Three
separate defects were hiding behind that:

1. **Every fixture contained literal backslash-n, not newlines.** The source read
   ``write_text("# Test Spec\\n\\n## Intent...")`` — an escaped backslash — so the specs were one
   long line. The `context.yaml` was written the same way, which means it was not parseable as the
   two-key mapping it was meant to be.
2. **The `context.yaml` used the wrong schema entirely.** It wrote ``archetype``/``effect`` keys;
   `DALResolver._parse_dal_from_context` reads ``operational.dal_level`` and nothing else. So the
   DAL_A boundary the test existed to create was never created, newlines or not.
3. **The comment said "Inject DAL matrix strictly disabling rule S02"** and no matrix was ever
   injected.

The spec fixture is now `tests/fixtures/good_spec.md`, chosen because it PASSES WITH WARNINGS —
that is the only outcome where strictness is observable, since `_print_summary` turns warnings into
exit 1 only when strict is in force. A spec that already fails exits 1 everywhere and proves
nothing, which is what the old minimal fixture did.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

#: Passes with warnings and no failures — see the module docstring for why that matters.
_SPEC = (Path(__file__).resolve().parents[3] / "fixtures" / "good_spec.md").read_text(
    encoding="utf-8"
)

_proj_counter = 0


def _unique_name(prefix: str = "test") -> str:
    """Generate unique project names to avoid DB collisions."""
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


def _project(tmp_path: Path, prefix: str) -> Path:
    runner = CliRunner()
    result = runner.invoke(app, ["init", _unique_name(prefix), "--path", str(tmp_path)])
    assert result.exit_code == 0, result.output
    return tmp_path


def _bind(directory: Path, dal: str) -> Path:
    """Declare `dal` for everything at or below `directory`, and drop a spec inside it."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "context.yaml").write_text(f"operational:\n  dal_level: {dal}\n", encoding="utf-8")
    spec = directory / "bound.md"
    spec.write_text(_SPEC, encoding="utf-8")
    return spec


def _check(project: Path, spec: Path) -> tuple[int, str]:
    result = CliRunner().invoke(app, ["check", str(spec), "--project", str(project)])
    return result.exit_code, result.output


class TestNestedDalZeroTolerance:
    """Story 7: a nested DAL declaration enforces zero tolerance on the same spec."""

    def test_an_unbound_spec_passes_with_warnings(self, tmp_path: Path) -> None:
        """The control. Without a DAL boundary, warnings are warnings and the run exits 0."""
        project = _project(tmp_path, "dal_chk")
        (project / "specs").mkdir(exist_ok=True)
        spec = project / "specs" / "free.md"
        spec.write_text(_SPEC, encoding="utf-8")

        code, output = _check(project, spec)

        assert code == 0, output
        assert "DAL: Unbound" in output
        assert "PASSED with warnings" in output

    def test_the_same_spec_under_dal_a_fails(self, tmp_path: Path) -> None:
        """Zero tolerance: identical content, identical warnings, exit 1 because DAL_A is strict."""
        project = _project(tmp_path, "dal_chk")
        spec = _bind(project / "src" / "critical", "DAL_A")

        code, output = _check(project, spec)

        assert code == 1, output
        assert "DAL: DAL_A" in output
        # Still only warnings — the exit code changed, not the findings. That is the whole claim.
        assert "PASSED with warnings" in output

    def test_a_non_strict_boundary_still_passes(self, tmp_path: Path) -> None:
        """The control that makes the test above mean STRICTNESS rather than merely BOUND.

        Without it, a regression that failed any spec under any `context.yaml` would look correct.
        `DALLevel.is_strict` is true for DAL_A and DAL_B only.
        """
        project = _project(tmp_path, "dal_chk")
        spec = _bind(project / "src" / "relaxed", "DAL_E")

        code, output = _check(project, spec)

        assert code == 0, output
        assert "DAL: DAL_E" in output

    def test_the_boundary_is_inherited_by_nested_paths(self, tmp_path: Path) -> None:
        """ "Nested" in the story title: the declaration sits above the spec, not beside it."""
        project = _project(tmp_path, "dal_chk")
        _bind(project / "src" / "critical", "DAL_A")
        deeper = project / "src" / "critical" / "sub" / "deeper"
        deeper.mkdir(parents=True)
        spec = deeper / "nested.md"
        spec.write_text(_SPEC, encoding="utf-8")

        code, output = _check(project, spec)

        assert code == 1, output
        assert "DAL: DAL_A" in output


class TestImplementUnderDal:
    """Story 8: `sw implement` under a strict DAL.

    > [!IMPORTANT]
    > **The DAL-override half of Story 8 is still NOT proven here** — filed as `TECH-041` rather
    > than faked or left implied. `sw implement` reaches the LLM before any code-level DAL
    > enforcement can run, so proving "implement triggers strict code-handler DAL overrides" needs
    > a scripted adapter of the kind `test_feature_decomposition_e2e.py` builds.
    >
    > What the old test actually exercised was **nothing**: it passed `"specs/test.md"` as a
    > relative path while the project lived in `tmp_path`, so `sw implement` exited 1 on
    > `Spec not found` — and `exit_code in (0, 1)` accepted that. It never entered the implement
    > path at all, let alone reached a DAL decision.
    """

    def test_implement_finds_the_spec_and_fails_at_the_provider(self, tmp_path: Path) -> None:
        """Narrow but real: the spec resolves, the pipeline is entered, the LLM is what is missing.

        This cannot pass on a mistyped path, which is the specific way its predecessor was hollow.
        """
        project = _project(tmp_path, "dal_impl")
        spec = _bind(project / "src" / "critical", "DAL_A")

        result = CliRunner().invoke(app, ["implement", str(spec), "--project", str(project)])

        assert result.exit_code == 1, result.output
        assert "Spec not found" not in result.output
        assert "No API key configured" in result.output
