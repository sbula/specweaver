import pytest

from specweaver.core.loom.commons.language.evaluator import EvaluatorDepthError, SchemaEvaluator


@pytest.fixture
def sample_schemas():
    return {
        "spring-boot": {
            "metadata": {"supported_languages": ["java", "kotlin"]},
            "decorators": {
                "RestController": "Handles HTTP requests",
                "GetMapping": "Maps HTTP GET",
                "SelfReferencing": "Expands to >>{SelfReferencing}<<"
            },
            "bases": {
                "JpaRepository": "Provides database operations"
            }
        },
        "fastapi": {
            "metadata": {"supported_languages": ["python"]},
            "decorators": {
                "app.get": "FastAPI GET Route"
            }
        }
    }


def test_schema_evaluator_translates_known_markers(sample_schemas):
    """Test standard mapping of dict elements to comment blocks."""
    evaluator = SchemaEvaluator(sample_schemas)
    markers = {
        "decorators": {"RestController": [], "GetMapping": ["'/api/v1'"]},
        "bases": {}
    }

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
    markers = {
        "decorators": {"SelfReferencing": []},
        "bases": {}
    }

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

