# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The artifacts a feature decomposition produces, and how they reach disk.

Split out of ``handlers/decompose.py`` by INT-US-21 SF-02 CB-2, which took that file to 586 lines
against a 450-line threshold and CB-3 adds more. Named for the contract it owns — the artifacts a
decomposition emits — rather than for what the code is, so it cannot accrete unrelated helpers.

``TECH-016`` has since landed (2026-08-12) and did what this note predicted: the uuid/tag and
lineage-event halves of the sequence now live in :mod:`~specweaver.core.flow.handlers.artifact_lineage`
and are called from here. What stays is what the note said would stay -- the YAML rendering, the
stub writer and the feature-name derivation, because the *head* of an artifact write differs at
every site.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


#: Suffix stripped when deriving a feature name from its spec filename (INT-US-21 FR-1 convention).
FEATURE_SPEC_STEM_SUFFIX = "_feature_spec"

#: Component names are authored by an LLM and become path segments, so they are validated before
#: ANY filesystem write (NFR-5). One constant, shared by the stub writer and the fan-out guard —
#: two copies of a security regex is one copy too many.
#:
#: ``\Z``, not ``$``: Python's ``$`` also matches immediately before a trailing newline, so the
#: shipped fan-out guard accepted ``"auth\n"`` — a legal filename on POSIX and a log-injection
#: vector, defeating the guard's own stated intent. Inherited defect, verified and fixed by
#: INT-US-21 SF-02 CB-2 (2026-07-26). Traversal was never possible: ``/``, ``\`` and ``.`` are
#: outside the class.
COMPONENT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+\Z")

#: Read as a FILE, never imported from `workspace/project` — `core/flow/context.yaml` `consumes`
#: does not list it, and tach permits `specweaver.workspace` wholesale so the import would not be
#: caught (SF-01 CB-1 decision).
COMPONENT_TEMPLATE_RELPATH = ".specweaver/templates/component_spec.md"

#: Used when the project was never scaffolded. Deliberately Jinja so both paths render identically.
FALLBACK_COMPONENT_SPEC = """\
# {{ component_name }} - Component Spec

> **Status**: DRAFT
> **Date**: {{ date }}
> **Layer**: Component (L2)
> **Parent Feature**: {{ parent_feature | default("N/A") }}

---

## 1. Purpose

{{ purpose | default("TODO: Describe the single responsibility.") }}

---

## 2. Contract

_What this component promises. The public interface._

## 3. Done Definition

_How we know it works._
"""


def feature_name_from_spec(spec_path: Path) -> str:
    """Derive a human-meaningful feature name from the spec filename."""
    return spec_path.stem.removesuffix(FEATURE_SPEC_STEM_SUFFIX) or spec_path.stem


def persist_decomposition(dumped: dict[str, Any], context: RunContext) -> tuple[Path, str]:
    """Write ``<spec_stem>_decomposition.yaml`` next to the spec. Returns (path, artifact uuid).

    Mirrors ``PlanSpecHandler``'s *sequence* — derive path, extract-or-generate uuid, tag, write —
    but NOT its serialization call (see the caller's D1 note). Raises ``OSError`` on write failure
    so the caller can honour D6.

    Re-running decomposition reuses the existing artifact's uuid rather than minting a new lineage
    identity for the same logical artifact.
    """
    import io

    from ruamel.yaml import YAML

    from specweaver.core.flow.handlers.artifact_lineage import derive_artifact_uuid, tag_content

    artifact_path = context.spec_path.with_name(context.spec_path.stem + "_decomposition.yaml")

    artifact_uuid = derive_artifact_uuid(artifact_path)

    yaml = YAML()
    yaml.default_flow_style = False
    buf = io.StringIO()
    yaml.dump(dumped, buf)

    content = tag_content(buf.getvalue(), artifact_uuid, "yaml")

    artifact_path.write_text(content, encoding="utf-8")
    logger.info(
        "[run_id=%s] Decomposition artifact written: %s (%d components)",
        context.run.run_id,
        artifact_path,
        len(dumped.get("components", [])),
    )
    return artifact_path, artifact_uuid


async def log_decomposition_lineage(context: RunContext, artifact_uuid: str) -> None:
    """Record the ``generated_decomposition`` lineage event when a telemetry DB is configured.

    **Never raises.** Lineage is telemetry, and by the time it runs the decomposition has already
    been paid for with an LLM call and durably written to disk. Letting a DB problem propagate hands
    it to ``execute``'s ``except Exception``, which returns ``ERROR`` with no ``output`` — throwing
    the plan away and violating the very rule D6 exists to enforce. Found by the CB-1 pre-commit
    gate (2026-07-26) against a non-bootstrapped database; the failure is logged at exception level
    so it is loud in logs while the run continues.
    """
    from specweaver.core.flow.handlers.artifact_lineage import log_artifact_lineage

    await log_artifact_lineage(context, artifact_uuid, "generated_decomposition")


def load_component_template(project_path: Path) -> str:
    """The scaffolded Jinja template, or a local skeleton when the project was never scaffolded."""
    try:
        return (project_path / COMPONENT_TEMPLATE_RELPATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.info(
            "No component template at %s — using the built-in skeleton",
            COMPONENT_TEMPLATE_RELPATH,
        )
        return FALLBACK_COMPONENT_SPEC


def _classify_stub(
    component: dict[str, Any], context: RunContext
) -> tuple[str, str, Path | None]:
    """`(report bucket, name, target)`. A non-None target means "safe to write".

    The three refusals, in the order they must be checked (`TECH-023` moved them out of
    :func:`write_component_stubs`; the ordering below is behaviour, not style).
    """
    name = component.get("component")
    if not name or not COMPONENT_NAME_PATTERN.match(str(name)):
        logger.warning(
            "[run_id=%s] Refusing to write a component spec for an invalid name: %r",
            context.run.run_id,
            name,
        )
        return "rejected", (str(name) if name else "<unnamed>"), None

    target = context.spec_path.with_name(f"{name}_spec.md")

    # Checked BEFORE is_file(), because the feature spec IS a file and would otherwise be
    # reported as `skipped` — telling the user a component spec exists where their own feature
    # spec sits. A component named `<feature>_feature` targets `<feature>_feature_spec.md`.
    # Distinct bucket because the remedy differs: `rejected` means fix the LLM output,
    # `collided` means rename the component.
    if target == context.spec_path:
        logger.warning(
            "[run_id=%s] Component '%s' would overwrite the feature spec itself (%s) — "
            "skipping; rename the component",
            context.run.run_id,
            name,
            target.name,
        )
        return "collided", name, None

    # is_file(), not exists(): a directory sitting at the stub path is an obstruction, not a
    # spec to preserve. exists() would label it "skipped" — reporting a user file that is not
    # there. Matches DraftSpecHandler's exists-skip, which is also is_file().
    if target.is_file():
        return "skipped", name, None

    return "", name, target


def _stub_vars(
    component: dict[str, Any], name: str, date_iso: str, feature_name: str
) -> dict[str, Any]:
    """Only pass variables that actually have a value.

    Jinja's `default()` filter fires on *undefined*, NOT on None — passing `purpose=None` would
    render the literal "None" into the user's spec instead of the template's TODO placeholder.
    """
    render_vars: dict[str, Any] = {"component_name": name, "date": date_iso}
    if feature_name:
        render_vars["parent_feature"] = feature_name
    if component.get("description"):
        render_vars["purpose"] = component["description"]
    return render_vars


def write_component_stubs(
    dumped: dict[str, Any], context: RunContext, feature_name: str
) -> dict[str, list[str]]:
    """Write ``<component>_spec.md`` beside the feature spec (D7), never overwriting.

    Returns a report with five disjoint lists — ``created``, ``skipped`` (a component spec already
    existed), ``rejected`` (name failed :data:`COMPONENT_NAME_PATTERN`), ``failed`` (write error)
    and ``collided`` (the stub path IS the feature spec).

    ``collided`` is separate from ``skipped`` on purpose: both leave a file untouched, but the
    remedy differs. ``skipped`` means a component spec is already authored — nothing to do.
    ``collided`` means the LLM named a component ``<feature>_feature``, whose stub path resolves to
    the feature spec itself, so the user must rename the component. Folding it into ``skipped``
    claimed a component spec existed where their own feature spec sat.

    **A stub problem never fails the step.** By the time this runs the decomposition has been paid
    for with an LLM call and the artifact is durably on disk; discarding that because one component
    name was malformed, or one file was unwritable, is the same defect the CB-1 gate found in the
    lineage path. Never-overwrite makes a re-run safe, the fan-out has its own hard name guard so
    nothing unsafe proceeds regardless, and every non-created component is named in the report
    rather than silently dropped (R/B C1.2).
    """
    from jinja2 import Template  # D3: an existing project dep, not a context.yaml module edge

    report: dict[str, list[str]] = {
        "created": [],
        "skipped": [],
        "rejected": [],
        "failed": [],
        "collided": [],
    }
    components = dumped.get("components") or []
    if not components:
        return report

    template = Template(load_component_template(context.project_path))
    date_iso = context.project_metadata.date_iso if context.project_metadata else ""

    for component in components:
        bucket, name, target = _classify_stub(component, context)
        if target is None:
            report[bucket].append(name)
            continue

        try:
            target.write_text(
                template.render(**_stub_vars(component, name, date_iso, feature_name)),
                encoding="utf-8",
            )
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning(
                "[run_id=%s] Could not write the component spec for '%s': %s",
                context.run.run_id,
                name,
                exc,
            )
            report["failed"].append(name)
            continue
        report["created"].append(name)

    logger.info(
        "[run_id=%s] Component specs: %d created, %d skipped, %d rejected, %d failed, %d collided",
        context.run.run_id,
        len(report["created"]),
        len(report["skipped"]),
        len(report["rejected"]),
        len(report["failed"]),
        len(report["collided"]),
    )
    return report


def build_dal_summary(
    dumped: dict[str, Any], artifact_path: Path, stub_report: dict[str, list[str]]
) -> str:
    """The human-readable half of FR-7 — `proposed_dal` per component, plus what reached disk.

    D2: no park surface renders ``StepResult.output`` today (R-4), and changing
    ``engine/display.py`` would touch shipped display used by every pipeline — wider than SF-02's
    remit. So the handler owns the text and SF-03's CLI journey owns the rendering. Naming the
    artifact file here is what lets a human review it before resuming (NFR-7).
    """
    components = dumped.get("components") or []
    lines = [f"Decomposition artifact: {artifact_path.name}"]

    if not components:
        lines.append("0 components proposed.")
    else:
        width = max(len(str(c.get("component") or "<unnamed>")) for c in components)
        lines.append(f"{len(components)} component(s), proposed DAL per component:")
        for component in components:
            name = str(component.get("component") or "<unnamed>")
            dal = component.get("proposed_dal") or "unrated"
            lines.append(f"  {name.ljust(width)}  {dal}")

    outcomes = ", ".join(f"{len(v)} {k}" for k, v in stub_report.items() if v)
    lines.append(f"Component specs: {outcomes or 'none written'}")
    return "\n".join(lines)
