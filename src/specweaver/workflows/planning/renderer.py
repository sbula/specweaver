# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Plan renderer — on-demand Markdown rendering from PlanArtifact.

The Plan is stored as YAML (primary, machine-consumable format).
When a HITL explicitly requests review, this renderer produces a
human-readable Markdown view. Reasoning is omitted by default
(available via ``verbose=True``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.workflows.planning.models import KNOWN_ARCHETYPES

if TYPE_CHECKING:
    from specweaver.workflows.planning.models import PlanArtifact


# ---------------------------------------------------------------------------
# Section renderers (extracted to keep C901 complexity ≤ 10)
# ---------------------------------------------------------------------------


def _render_header(plan: PlanArtifact) -> list[str]:
    """Render the plan header with spec metadata."""
    return [
        f"# Plan: {plan.spec_name}",
        f"\n**Spec**: `{plan.spec_path}`",
        f"**Generated**: {plan.timestamp}",
        f"**Confidence**: {plan.confidence}/100",
        f"**Spec Hash**: `{plan.spec_hash[:12]}...`",
    ]


def _render_architecture(plan: PlanArtifact) -> list[str]:
    """Render the architecture section (if present)."""
    if not plan.architecture:
        return []
    arch = plan.architecture
    parts = [
        "\n## Architecture\n",
        f"- **Module Layout**: {arch.module_layout}",
        f"- **Dependency Direction**: {arch.dependency_direction}",
    ]
    archetype_warning = ""
    if arch.archetype not in KNOWN_ARCHETYPES:
        archetype_warning = " ⚠️ (unknown archetype)"
    parts.append(f"- **Archetype**: `{arch.archetype}`{archetype_warning}")
    if arch.patterns:
        parts.append(f"- **Patterns**: {', '.join(arch.patterns)}")
    return parts


def _render_tech_stack(plan: PlanArtifact) -> list[str]:
    """Render the tech stack table (if present)."""
    if not plan.tech_stack:
        return []
    parts = [
        "\n## Tech Stack\n",
        "| Category | Choice | Rationale |",
        "|----------|--------|-----------|",
    ]
    for ts in plan.tech_stack:
        alts = (
            f" (vs. {', '.join(ts.alternatives_considered)})" if ts.alternatives_considered else ""
        )
        parts.append(f"| {ts.category} | {ts.choice} | {ts.rationale}{alts} |")
    return parts


def _render_file_layout(plan: PlanArtifact) -> list[str]:
    """Render the file layout table with complexity indicator."""
    parts = ["\n## File Layout\n"]
    if not plan.file_layout:
        parts.append("*No files specified.*")
        return parts
    count = len(plan.file_layout)
    if count <= 5:
        complexity = "🟢 Simple"
    elif count <= 15:
        complexity = "🟡 Moderate"
    else:
        complexity = "🔴 Consider splitting"
    parts.append(f"**{count} files** — {complexity}\n")
    parts.append("| Action | Path | Purpose |")
    parts.append("|--------|------|---------|")
    for fc in plan.file_layout:
        parts.append(f"| {fc.action} | `{fc.path}` | {fc.purpose} |")
    return parts


def _render_constraints(plan: PlanArtifact) -> list[str]:
    """Render the constraints section (if present)."""
    if not plan.constraints:
        return []
    parts = ["\n## Constraints\n"]
    for cn in plan.constraints:
        parts.append(f"- **{cn.source}**: {cn.constraint} → _{cn.impact}_")
    return parts


def _render_tasks(plan: PlanArtifact) -> list[str]:
    """Render the implementation tasks section (if present)."""
    if not plan.tasks:
        return []
    parts = ["\n## Implementation Tasks\n"]
    for i, task in enumerate(plan.tasks, 1):
        deps = f" (depends on: {', '.join(task.dependencies)})" if task.dependencies else ""
        parts.append(f"{i}. **{task.name}**{deps}")
        parts.append(f"   {task.description}")
        if task.files:
            parts.append(f"   Files: {', '.join(f'`{f}`' for f in task.files)}")
    return parts


def _render_test_expectations(plan: PlanArtifact) -> list[str]:
    """Render the test expectations table (if present)."""
    if not plan.test_expectations:
        return []
    parts = [
        "\n## Test Expectations\n",
        "| Name | Category | Function | Expected |",
        "|------|----------|----------|----------|",
    ]
    for te in plan.test_expectations:
        parts.append(
            f"| {te.name} | {te.category} | `{te.function_under_test}` | {te.expected_behavior} |"
        )
    return parts


def _render_mockups(plan: PlanArtifact) -> list[str]:
    """Render the UI mockups section (if present)."""
    if not plan.mockups:
        return []
    parts = ["\n## UI Mockups\n"]
    for m in plan.mockups:
        parts.append(f"- **{m.screen_name}**: {m.description}")
        parts.append(f"  [Preview]({m.preview_url})")
    return parts


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------


def render_plan_markdown(plan: PlanArtifact, *, verbose: bool = False) -> str:
    """Render a ``PlanArtifact`` as human-readable Markdown.

    Sections: Architecture, Tech Stack, File Layout, Constraints,
    Implementation Tasks, Test Expectations, UI Mockups (if any).

    Args:
        plan: The plan to render.
        verbose: If True, include the reasoning section.

    Returns:
        Markdown string.
    """
    parts: list[str] = []
    parts.extend(_render_header(plan))
    parts.extend(_render_architecture(plan))
    parts.extend(_render_tech_stack(plan))
    parts.extend(_render_file_layout(plan))
    parts.extend(_render_constraints(plan))
    parts.extend(_render_tasks(plan))
    parts.extend(_render_test_expectations(plan))
    parts.extend(_render_mockups(plan))

    if verbose and plan.reasoning:
        parts.append("\n## Reasoning\n")
        parts.append(plan.reasoning)

    return "\n".join(parts) + "\n"
