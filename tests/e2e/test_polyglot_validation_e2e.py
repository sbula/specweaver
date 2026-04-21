# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.assurance.validation.models import Status
from specweaver.assurance.validation.rules.code.c09_traceability import TraceabilityRule

# Using TraceabilityRule directly, simulating the pipeline executor behavior
# to create a fully integrated end-to-end trace from Spec > Rule > AnalyzerFactory > TreeSitter Parsers.


def test_e2e_polyglot_traceability(tmp_path: Path) -> None:
    """E2E verification of polyglot traceability.

    A spec defining FR-1, FR-2, FR-3 is validated against a mixed polyglot
    repository containing TypeScript, Java, and Rust tests bridging the trace gap.
    """
    root = tmp_path / "polyglot_project"
    root.mkdir()

    (root / "pyproject.toml").touch()

    # 1. Provide a Spec
    specs_dir = root / "specs"
    specs_dir.mkdir()
    (specs_dir / "design.md").write_text("Requirements: FR-1, FR-2, FR-3")

    # 2. Provide Polyglot source tests
    # TypeScript
    ts_dir = root / "frontend"
    ts_dir.mkdir()
    (ts_dir / "auth.test.ts").write_text(
        "describe('Auth', () => {\n"
        "  // @trace(FR-1)\n"
        "  it('should format correctly', () => {});\n"
        "});\n"
    )

    # Java
    java_dir = root / "backend_billing"
    java_dir.mkdir()
    (java_dir / "BillingTest.java").write_text(
        "class BillingTest {\n    // @trace(FR-2)\n    void testInvoice() {}\n}\n"
    )

    # Rust
    rust_dir = root / "core_crypto"
    rust_dir.mkdir()
    (rust_dir / "crypto_scenarios.rs").write_text("// @trace(FR-3)\nfn test_hashing() {}\n")

    # Instantiate the unified Traceability Rule
    rule = TraceabilityRule()

    result = rule.check(spec_text="", spec_path=root / "specs" / "design.md")

    # Validate entire engine passed cleanly
    assert result.status == Status.PASS
    assert (
        "Requirements successfully traced" in result.message
        or "All 3 requirements" in result.message
    )
