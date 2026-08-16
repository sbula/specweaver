# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where the delivered-claim guard meets the two things it depends on. TECH-053.

Proves: TECH-053 FR-2, TECH-053 FR-3

The unit tests drive both rules against synthetic registries. Two things they cannot reach:

**The `check_fr_coverage` seam.** This check does not own an FR grammar — it loads the one already
in the repo (`_fr_reader()`). That coupling exists *because* a second parser was written first and
was wrong: reading table rows only, it reported `C-SENS-02` and `D-SENS-03` as declaring no
requirements when they declare twelve between them, as bullets. A synthetic design proves the
reader is called; only the real registry proves the two readers agree about it.

**The gate seam.** `quality.py doc` shells out with the venv interpreter and maps the exit code.
Mocking that would test the mock.

**No e2e**, for the same reason as `TECH-051` CB-3: `quality.py` is a developer gate rather than a
`sw` command, and an e2e would be this subprocess call from a different directory.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class TestAgreesWithTheFrLedger:
    """FR-2 — the two readers of a design document reach the same verdict on every capability."""

    def test_no_capability_is_reported_that_the_ledger_can_read_frs_for(self) -> None:
        """Every "declares no FRs" finding is confirmed against `check_fr_coverage` itself.

        This is the assertion the first draft would have failed. It is run over the **real**
        registry rather than a fixture, because the disagreement was in two real designs whose
        bullet-style FR lists no synthetic case would have thought to imitate.
        """
        claims = _load("check_delivered_claims")
        coverage = _load("check_fr_coverage")
        roadmap = REPO_ROOT / "docs" / "roadmap"
        features = roadmap / "features"

        disputed = []
        for finding in claims.unverifiable_findings(roadmap):
            if finding.reason != "design declares no FRs":
                continue
            design = coverage.find_design_doc(features, finding.capability)
            frs, _ = coverage.declared_frs_from_text(
                design.read_text(encoding="utf-8"), design.name
            )
            if frs:
                disputed.append((finding.capability, frs))

        assert not disputed, (
            "reported as declaring no FRs, but the ledger reads some — the two parsers "
            f"disagree: {disputed}"
        )

    def test_every_no_design_finding_really_has_no_design(self) -> None:
        """[Boundary] the other half of the same agreement, and the cheaper half to get wrong."""
        claims = _load("check_delivered_claims")
        coverage = _load("check_fr_coverage")
        features = REPO_ROOT / "docs" / "roadmap" / "features"

        missing = [
            f.capability
            for f in claims.unverifiable_findings(REPO_ROOT / "docs" / "roadmap")
            if f.reason == "no design document"
        ]

        assert missing, "the baseline says there are some; if this is empty the walk is broken"
        for capability in missing:
            assert coverage.find_design_doc(features, capability) is None, capability


class TestTheDocGateRunsTheCheck:
    """FR-3 — a finding reaches the gate's exit code, with its cause attached."""

    def test_quality_doc_includes_the_delivered_claims_check(self) -> None:
        """[Happy] registered and resolving, not merely present in the MATRIX table."""
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "quality.py"),
                "doc",
                "--only",
                "delivered_claims",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )

        assert result.returncode == 0, result.stdout + result.stderr
        assert "delivered_claims" in result.stdout

    def test_growth_past_the_baseline_exits_one_and_names_the_cause(self) -> None:
        """[Hostile] the ratchet, driven through the real script with a baseline of zero.

        Uses `--baseline 0` rather than a doctored registry: the finding set is the live one, so
        this also proves the reported causes survive the subprocess boundary intact.
        """
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "check_delivered_claims.py"),
                "--baseline",
                "0",
            ],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )

        assert result.returncode == 1
        assert "no design document" in result.stdout
        assert "was 0" in result.stdout

    def test_a_registry_it_cannot_find_exits_two(self, tmp_path: Path) -> None:
        """[Hostile] `TECH-032` — not zero, so "I could not look" differs from "all clear"."""
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "check_delivered_claims.py"),
                "--root",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 2
        assert "could not run" in result.stderr
