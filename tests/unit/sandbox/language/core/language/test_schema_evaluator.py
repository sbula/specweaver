# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import pytest

from specweaver.sandbox.language.core.evaluator import EvaluatorDepthError, SchemaEvaluator


@pytest.fixture
def sample_schemas():
    return {
        "spring-boot": {
            "metadata": {"supported_languages": ["java", "kotlin"]},
            "decorators": {
                "RestController": "Handles HTTP requests",
                "GetMapping": "Maps HTTP GET",
                "SelfReferencing": "Expands to >>{SelfReferencing}<<",
            },
            "bases": {"JpaRepository": "Provides database operations"},
        },
        "fastapi": {
            "metadata": {"supported_languages": ["python"]},
            "decorators": {"app.get": "FastAPI GET Route"},
        },
    }


def test_schema_evaluator_translates_known_markers(sample_schemas):
    """Test standard mapping of dict elements to comment blocks."""
    evaluator = SchemaEvaluator(sample_schemas)
    markers = {"decorators": {"RestController": [], "GetMapping": ["'/api/v1'"]}, "bases": {}}

    result = evaluator.evaluate_markers("java", "spring-boot", markers)

    # Needs to be prefixed with `//` for java
    assert "// [Framework Eval] Handles HTTP requests" in result
    assert "// [Framework Eval] Maps HTTP GET" in result


def test_schema_evaluator_skips_unsupported_languages(sample_schemas):
    """Test that NFR-2 successfully skips applying Java logic to Python files."""
    evaluator = SchemaEvaluator(sample_schemas)
    markers = {"decorators": {"RestController": []}, "bases": {}}

    # Try to evaluate spring-boot against python AST
    result = evaluator.evaluate_markers("python", "spring-boot", markers)
    assert result == ""  # Safely returns empty


def test_schema_evaluator_language_comment_prefixes(sample_schemas):
    evaluator = SchemaEvaluator(sample_schemas)
    markers = {"decorators": {"app.get": []}, "bases": {}}

    result = evaluator.evaluate_markers("python", "fastapi", markers)

    assert "# [Framework Eval] FastAPI GET Route" in result


def test_schema_evaluator_recursion_protection(sample_schemas):
    """Test that a cyclic mapping triggers the max depth 5 termination correctly."""
    evaluator = SchemaEvaluator(sample_schemas)
    markers = {"decorators": {"SelfReferencing": []}, "bases": {}}

    with pytest.raises(EvaluatorDepthError, match="Maximum cyclic evaluator depth"):
        evaluator.evaluate_markers("java", "spring-boot", markers)


def test_schema_evaluator_comment_prefix_mapping():
    evaluator = SchemaEvaluator({})
    assert evaluator._get_comment_prefix("python") == "#"
    assert evaluator._get_comment_prefix("ruby") == "#"
    assert evaluator._get_comment_prefix("yaml") == "#"
    assert evaluator._get_comment_prefix("shell") == "#"

    assert evaluator._get_comment_prefix("java") == "//"
    assert evaluator._get_comment_prefix("typescript") == "//"
    assert evaluator._get_comment_prefix("rust") == "//"
    assert evaluator._get_comment_prefix("cpp") == "//"
    assert evaluator._get_comment_prefix("unknownXYZ") == "//"


class TestMarkersCarryingArguments:
    """An annotation with arguments is looked up by its name, and keeps the arguments.

    Proves: TECH-065 FR-1, TECH-065 FR-2

    Parsers extract a marker with its argument list attached — `GetMapping("/orders/{id}")` — while
    every schema key is a bare name. So `@RestController` unrolled and `@GetMapping` on the same
    class did not, and the Actix sample unrolled nothing at all because both its route decorators
    take a path. Roughly half of each shipped schema was unreachable, and it is the half that
    describes routing.

    **The decision the ticket named was whether arguments are data or noise, and they are data.** A
    route path is exactly what an unrolled description should carry, so the arguments are exposed to
    the template as `>>{args}<<` rather than discarded to make the lookup work.

    Exact match still wins. `actix-web.yaml` ships `derive(Clone)` as a literal key, so a schema that
    already opted into arguments keeps its meaning.
    """

    def test_a_marker_with_arguments_matches_its_bare_name(self) -> None:
        evaluator = SchemaEvaluator({"spring": {"annotations": {"GetMapping": "HTTP GET"}}})

        out = evaluator.evaluate_markers(
            "java", "spring", {"annotations": ['GetMapping("/orders/{id}")']}
        )

        assert "HTTP GET" in out

    def test_the_arguments_are_available_to_the_template(self) -> None:
        """Throwing the path away would trade one silent loss for another."""
        evaluator = SchemaEvaluator(
            {"spring": {"annotations": {"GetMapping": "HTTP GET >>{args}<<"}}}
        )

        out = evaluator.evaluate_markers(
            "java", "spring", {"annotations": ['GetMapping("/orders/{id}")']}
        )

        assert "/orders/{id}" in out

    def test_an_exact_key_still_wins(self) -> None:
        """`actix-web.yaml` ships `derive(Clone)`; a bare-name fallback must not override it."""
        evaluator = SchemaEvaluator(
            {"actix": {"decorators": {"derive(Clone)": "impl Clone", "derive": "WRONG"}}}
        )

        out = evaluator.evaluate_markers("rust", "actix", {"decorators": ["derive(Clone)"]})

        assert "impl Clone" in out
        assert "WRONG" not in out

    def test_a_bare_marker_is_unaffected(self) -> None:
        """The control. The argument-less subset was the half that always worked."""
        evaluator = SchemaEvaluator({"spring": {"annotations": {"RestController": "@Controller"}}})

        out = evaluator.evaluate_markers("java", "spring", {"annotations": ["RestController"]})

        assert "@Controller" in out

    def test_an_unknown_marker_still_matches_nothing(self) -> None:
        """Stripping arguments must not turn every unknown annotation into a partial hit."""
        evaluator = SchemaEvaluator({"spring": {"annotations": {"GetMapping": "HTTP GET"}}})

        out = evaluator.evaluate_markers("java", "spring", {"annotations": ['Unknown("/x")']})

        assert out == ""
