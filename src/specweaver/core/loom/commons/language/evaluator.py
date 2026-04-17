# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import re
from typing import Any

MAX_EVALUATOR_DEPTH = 5


class EvaluatorDepthError(Exception):
    """Raised when schema evaluation exceeds the max depth or hits a cyclic dependency."""


class SchemaEvaluator:
    """Evaluates AST markers against declarative schemas to produce LLM string representations."""

    def __init__(self, schemas: dict[str, Any]) -> None:
        self._schemas = schemas

    def _get_comment_prefix(self, language: str) -> str:
        """Return the standard language line-comment format."""
        if language in ("python", "ruby", "yaml", "shell", "rust"):
            if language == "rust":
                return "//"
            return "#"
        return "//"

    def _resolve_template(
        self, template: str, category_dict: dict[str, Any], depth: int, visited: set[str]
    ) -> str:
        """Resolve recursive marker variables safely with depth limits."""
        if depth > MAX_EVALUATOR_DEPTH:
            raise EvaluatorDepthError(f"Maximum cyclic evaluator depth exceeded ({MAX_EVALUATOR_DEPTH})")

        matches = re.findall(r">>\{([^}]+)\}<<", template)
        result = template

        for key in matches:
            if key in visited:
                raise EvaluatorDepthError(f"Maximum cyclic evaluator depth or circular loop for '{key}'")

            if key in category_dict:
                visited.add(key)
                resolved_sub = self._resolve_template(
                    str(category_dict[key]), category_dict, depth + 1, visited
                )
                result = result.replace(f">>{{{key}}}<<", resolved_sub)
                visited.remove(key)

        return result

    def evaluate_markers(self, language: str, markers: dict[str, Any]) -> str:
        """Translate extracted AST dictionary markers to formatted explanation comments.

        Args:
            language: The language being evaluated (e.g. 'java', 'python').
            markers: The dictionary extracted from CodeStructureInterface frameworks.

        Returns:
            A block of formatted comments representing the unrolled reality.
        """
        lines = []
        prefix = self._get_comment_prefix(language)
        lang_schema = self._schemas.get(language, {})

        for category, items in markers.items():
            schema_category = lang_schema.get(category, {})
            for marker_name in items:
                if marker_name in schema_category:
                    template = str(schema_category[marker_name])
                    resolved_desc = self._resolve_template(template, schema_category, 0, {marker_name})
                    lines.append(f"{prefix} [Framework Eval] {resolved_desc}")

        return "\n".join(lines)
