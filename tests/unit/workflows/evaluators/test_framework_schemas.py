"""Tests for native ecosystem framework schemas."""

from specweaver.workflows.evaluators.loader import load_evaluator_schemas


def test_load_all_ecosystem_frameworks() -> None:
    """Verifies that all packaged ecosystem YAMLs parse correctly into dictionaries."""
    schemas = load_evaluator_schemas()

    # Assert critical frameworks loaded
    assert "spring-boot" in schemas
    assert "nestjs" in schemas
    assert "fastapi" in schemas
    assert "actix-web" in schemas
    assert "quarkus" in schemas

    # Assert metadata parses explicitly
    assert "metadata" in schemas["spring-boot"]
    assert schemas["spring-boot"]["metadata"]["supported_languages"] == ["java", "kotlin"]

    # Assert structural meta-annotations are correctly configured
    assert "decorators" in schemas["spring-boot"]
    assert schemas["spring-boot"]["decorators"]["RestController"] == "@Controller\n@ResponseBody"

    # Assert Python Fastapi maps correctly
    assert "decorators" in schemas["fastapi"]
    assert schemas["fastapi"]["decorators"]["app.get"] == "@api_route(method='GET')"

    # Assert Rust Proc-Macros mirror correctly
    assert "decorators" in schemas["actix-web"]
    assert (
        schemas["actix-web"]["decorators"]["derive(Clone)"]
        == "impl Clone for >>{Target}<< {\n    fn clone(&self) -> Self\n}"
    )
