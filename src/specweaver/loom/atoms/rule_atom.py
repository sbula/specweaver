# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""RuleAtom -- adapts a validation Rule to the Atom interface.

Bridges Rule.check(text, path) -> Atom.run(context) so validation rules
are composable like any other atom in the sub-pipeline.

Architecture:
    RuleAtom lives in loom/atoms/ because it IS an Atom. It consumes
    from validation/ for the Rule ABC, which is allowed (atoms consume
    commons, and validation is pure-logic).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.loom.atoms.base import Atom, AtomResult, AtomStatus
from specweaver.validation.models import Status

if TYPE_CHECKING:
    from specweaver.validation.models import Rule

logger = logging.getLogger(__name__)


class RuleAtom(Atom):
    """Adapts a validation Rule to the Atom interface.

    Takes a Rule instance and wraps its check() method in the
    Atom.run() contract, mapping RuleResult statuses to AtomStatus.

    Status mapping:
        PASS, WARN, SKIP -> AtomStatus.SUCCESS
        FAIL             -> AtomStatus.FAILED
        Exception        -> AtomStatus.FAILED (with error message)
    """

    def __init__(self, rule: Rule) -> None:
        self._rule = rule

    def run(self, context: dict[str, Any]) -> AtomResult:
        """Execute the wrapped rule.

        Expected context keys:
            spec_text: str -- the spec content to validate.
            spec_path: Path | None -- optional path to spec file.

        Returns:
            AtomResult with status, message, and exports.rule_result.
        """
        spec_text = context.get("spec_text", "")
        spec_path = context.get("spec_path")

        try:
            result = self._rule.check(spec_text, spec_path)
        except Exception as exc:
            logger.exception(
                "RuleAtom: rule '%s' (%s) crashed",
                self._rule.rule_id,
                self._rule.name,
            )
            return AtomResult(
                status=AtomStatus.FAILED,
                message=f"{self._rule.rule_id}: crashed: {type(exc).__name__}: {exc}",
                exports={},
            )

        atom_status = AtomStatus.FAILED if result.status == Status.FAIL else AtomStatus.SUCCESS

        return AtomResult(
            status=atom_status,
            message=f"{result.rule_id}: {result.message}",
            exports={"rule_result": result},
        )
