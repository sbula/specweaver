"""LanguageAtom — engine-level language detection and conversion.

The Engine uses LanguageAtom for language detection and scenario formatting
as part of pipeline steps to maintain the Atom Proxy architectural pattern.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.base import Atom, AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class LanguageAtom(Atom):
    """Engine-level language capability provider."""

    __test__ = False

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    def run(self, context: dict[str, Any]) -> AtomResult:
        """Dispatch to the appropriate intent based on context.

        Context must contain:
            intent: str — "detect_language" or "convert_scenario".
        """
        intent = context.get("intent")
        if intent is None:
            return AtomResult(
                status=AtomStatus.FAILED,
                message="Missing 'intent' in context.",
            )

        if intent == "detect_language":
            from specweaver.sandbox.language.core._detect import detect_language

            lang = detect_language(self._cwd)
            return AtomResult(
                status=AtomStatus.SUCCESS,
                message=f"Detected language: {lang}",
                exports={"language": lang},
            )

        elif intent == "convert_scenario":
            stem = context.get("stem")
            scenario_set = context.get("scenario_set")
            if not stem or not scenario_set:
                return AtomResult(
                    status=AtomStatus.FAILED, message="Missing 'stem' or 'scenario_set' in context."
                )

            from specweaver.sandbox.language.core.scenario_converter_factory import (
                create_scenario_converter,
            )

            converter = create_scenario_converter(self._cwd)
            content = converter.convert(scenario_set)
            output_path = converter.output_path(stem, self._cwd)

            return AtomResult(
                status=AtomStatus.SUCCESS,
                message="Scenario converted",
                exports={"content": content, "output_path": str(output_path)},
            )

        return AtomResult(status=AtomStatus.FAILED, message=f"Unknown intent: {intent!r}")
