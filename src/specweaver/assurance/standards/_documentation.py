# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Turning a documented/total count into a standards verdict.

The bands are a *policy* — what counts as a project's documentation convention — so they live in
one place, where changing them changes both the Python docstring analyzer and the JavaScript JSDoc
analyzer.
"""

from __future__ import annotations

from specweaver.assurance.standards.analyzer import CategoryResult

#: Ratio thresholds, highest first. A project at or above a threshold takes that label.
_COVERAGE_BANDS = ((0.9, "full"), (0.5, "high"), (0.2, "low"), (0.0, "none"))


def coverage_band(documented: int, total: int) -> str | None:
    """The band this ratio falls into, or None when there was nothing to measure.

    None rather than `"none"` for an empty sample: a project with no functions has not *failed* to
    document them, and reporting `none` would read as a finding against it.
    """
    if total <= 0:
        return None
    ratio = documented / total
    return next(label for threshold, label in _COVERAGE_BANDS if ratio >= threshold)


def documentation_result(category: str, documented: int, total: int) -> CategoryResult:
    """A `CategoryResult` for a documentation-coverage measurement."""
    band = coverage_band(documented, total)
    return CategoryResult(
        category=category,
        dominant={"coverage": band} if band else {},
        confidence=documented / total if total > 0 else 0.0,
        sample_size=total,
    )
