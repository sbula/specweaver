# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Turning a CLI spec argument into a path on disk.

Separate from `cli.py`, which would otherwise run past its 600-line RED threshold. Named for the
contract it owns — argument-to-path resolution — rather than for what the code is, so it cannot
accrete unrelated CLI helpers.

The rules differ per pipeline, and the order matters: an argument that already names an existing
file always wins, so an explicit path works for every pipeline without a special case.
"""

from __future__ import annotations

from pathlib import Path

from specweaver.core.flow.handlers.draft import FEATURE_SPEC_SUFFIX


def derive_feature_spec_path(name: str, project_path: Path) -> Path | None:
    """``specs/<name>_feature_spec.md`` for a plain feature name, else ``None``.

    ``FEATURE_SPEC_SUFFIX`` is **imported**, never re-spelled: `DraftFeatureHandler` errors loudly
    when ``context.spec_path`` does not match it, so a second literal here would drift and trip that
    guard on every drafting run.

    Returns ``None`` — deliberately falling through to the caller's literal-path branch, which
    fails later with a clear message — when the argument is not a plain filename. A bare name
    becomes a path segment, so ``..`` or a separator would otherwise escape ``specs/``.
    """
    if not name or "/" in name or "\\" in name or Path(name).name != name:
        return None
    stem = name[: -len(FEATURE_SPEC_SUFFIX)] if name.endswith(FEATURE_SPEC_SUFFIX) else name
    if not stem or stem in {".", ".."}:
        return None
    return project_path / "specs" / f"{stem}{FEATURE_SPEC_SUFFIX}"


def resolve_spec_path(
    pipeline_name: str,
    spec_or_module: str,
    project_path: Path,
) -> Path:
    """Resolve the spec argument based on pipeline type.

    For validate-style pipelines:  treat as direct file path.
    For new_feature-style:         treat as module name, derive spec path.
    """
    # If it looks like an existing file, use it directly
    spec_path = Path(spec_or_module)
    if spec_path.exists():
        return spec_path

    # For new_feature pipelines, derive from module name
    if pipeline_name == "new_feature":
        derived = project_path / "specs" / f"{spec_or_module}_spec.md"
        return derived

    # The same courtesy for the feature-decomposition journey.
    if pipeline_name == "feature_decomposition":
        feature_spec = derive_feature_spec_path(spec_or_module, project_path)
        if feature_spec is not None:
            return feature_spec

    # Try relative to project
    relative = project_path / spec_or_module
    if relative.exists():
        return relative

    # Fall back to the literal path (will fail later with clear message)
    return spec_path
