# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The check registry — which checks exist, what they run, and what paths they see.

Extracted from `quality.py` when adding `audit_matrix` pushed that file past the 600-line RED
threshold its own `file_sizes` check enforces. The registry is the part that grows every time a
guardrail is added, so it is the part that belongs on its own.

`Check` and the runners are passed IN rather than imported: `quality.py` owns both, and importing
them back from here would make the pair circular. Same `_load_sibling` shape as
`_quality_runners.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType


def build(make: Any, _r: ModuleType) -> dict[str, Any]:
    """Every check, keyed by name.

    `make` is `quality.Check` — passed in as a lowercase factory rather than bound to its class
    name, which would need an `N803` suppression, and this repo ratchets those.
    `_r` is `_quality_runners`.
    """
    return {
        # `scripts/` is included so the gate lints itself — it was previously unlinted by anything.
        "ruff": make("ruff", ("src", "tests", "scripts"), _r._ruff),
        "format": make("format", ("src", "tests", "scripts"), _r._format),
        "mypy": make("mypy", ("src",), _r._mypy),
        "tach": make("tach", ("src",), _r._tach, ignores_paths=True),
        # `script=` is not decoration: it is the pre-flight that reports MISSING instead of letting
        # the shell-out fail with a confusing error. This entry declared None while its runner
        # shells out to check_complexity.py, so complexipy alone lacked that guard (`TECH-037`).
        "complexipy": make("complexipy", ("src",), _r._complexipy, script="check_complexity.py"),
        "file_sizes": make(
            "file_sizes", ("src", "tests", "scripts"), _r._file_sizes, script="check_file_sizes.py"
        ),
        "test_basenames": make(
            "test_basenames", ("tests",), _r._test_basenames, script="check_test_basenames.py"
        ),
        "useless_asserts": make(
            "useless_asserts", ("tests",), _r._useless_asserts, script="check_useless_asserts.py"
        ),
        "suppressions": make(
            "suppressions", ("src",), _r._suppressions, script="check_suppressions.py"
        ),
        "comment_provenance": make(
            "comment_provenance",
            ("src",),
            _r._comment_provenance,
            script="check_comment_provenance.py",
        ),
        "class_health": make(
            "class_health", ("src",), _r._class_health, script="check_class_health.py"
        ),
        "coupling": make("coupling", ("src",), _r._coupling, script="check_coupling.py"),
        "cycles": make("cycles", ("src",), _r._cycles, script="check_coupling.py"),
        "duplication": make(
            "duplication",
            ("src",),
            _r._duplication,
            ignores_paths=True,
            script="check_duplication.py",
        ),
        "test_collection": make(
            "test_collection",
            ("tests",),
            _r._whole_repo("check_test_collection.py"),
            ignores_paths=True,
            script="check_test_collection.py",
        ),
        "xfail_blockers": make(
            "xfail_blockers",
            ("tests", "docs"),
            _r._xfail_blockers,
            ignores_paths=True,
            script="check_xfail_blockers.py",
        ),
        "roadmap_placement": make(
            "roadmap_placement",
            ("docs",),
            _r._whole_repo("check_roadmap_placement.py"),
            ignores_paths=True,
            script="check_roadmap_placement.py",
        ),
        "delivered_claims": make(
            "delivered_claims",
            ("docs",),
            _r._whole_repo("check_delivered_claims.py"),
            ignores_paths=True,
            script="check_delivered_claims.py",
        ),
        "retirement_targets": make(
            "retirement_targets",
            ("docs",),
            _r._whole_repo("check_retirement_targets.py"),
            ignores_paths=True,
            script="check_retirement_targets.py",
        ),
        "roadmap_sync": make(
            "roadmap_sync",
            ("docs",),
            _r._whole_repo("check_roadmap_sync.py"),
            ignores_paths=True,
            script="check_roadmap_sync.py",
        ),
        "skill_sync": make(
            "skill_sync",
            (".agents",),
            _r._whole_repo("check_skill_sync.py"),
            ignores_paths=True,
            script="check_skill_sync.py",
        ),
        "skill_references": make(
            "skill_references",
            (".agents", "docs"),
            _r._whole_repo("check_skill_references.py"),
            ignores_paths=True,
            script="check_skill_references.py",
        ),
        "fr_sweep": make(
            "fr_sweep",
            ("docs",),
            _r._whole_repo("check_fr_sweep.py"),
            ignores_paths=True,
            script="check_fr_sweep.py",
        ),
        "nfr_sweep": make(
            "nfr_sweep",
            ("docs",),
            _r._whole_repo("check_nfr_sweep.py"),
            ignores_paths=True,
            script="check_nfr_sweep.py",
        ),
        "entry_depth": make(
            "entry_depth",
            ("docs",),
            _r._whole_repo("_entry_depth.py"),
            ignores_paths=True,
            script="_entry_depth.py",
        ),
        "proof_tier": make(
            "proof_tier",
            ("docs",),
            _r._whole_repo("check_proof_tier.py"),
            ignores_paths=True,
            script="check_proof_tier.py",
        ),
        "audit_matrix": make(
            "audit_matrix",
            ("docs",),
            _r._whole_repo("check_audit_matrix.py"),
            ignores_paths=True,
            script="check_audit_matrix.py",
        ),
        # `tests` is in scope so R5 (e2e naming) can see e2e files; R2 stays src/scripts-only.
        "conventions": make(
            "conventions", ("src", "tests"), _r._conventions, script="check_conventions.py"
        ),
    }
