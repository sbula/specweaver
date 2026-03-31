from specweaver.llm.lineage import (
    extract_artifact_uuid,
    wrap_artifact_tag,
)


def test_extract_artifact_uuid_success_python_comment():
    content = "# sw-artifact: 123e4567-e89b-12d3-a456-426614174000\nprint('hello')"
    assert extract_artifact_uuid(content) == "123e4567-e89b-12d3-a456-426614174000"


def test_extract_artifact_uuid_success_markdown_comment():
    content = "<!-- sw-artifact: 123e4567-e89b-12d3-a456-426614174000 -->\n# Header"
    assert extract_artifact_uuid(content) == "123e4567-e89b-12d3-a456-426614174000"


def test_extract_artifact_uuid_case_insensitive():
    content = "// SW-ARTIFACT: 123e4567-e89b-12d3-a456-426614174000"
    assert extract_artifact_uuid(content) == "123e4567-e89b-12d3-a456-426614174000"


def test_extract_artifact_uuid_not_found():
    content = "print('hello world')"
    assert extract_artifact_uuid(content) is None


def test_extract_artifact_uuid_malformed_uuid():
    content = "# sw-artifact: 123e-notauuid-456"
    assert extract_artifact_uuid(content) is None


def test_wrap_artifact_tag_python():
    assert wrap_artifact_tag("my-uuid-123", "python") == "# sw-artifact: my-uuid-123"


def test_wrap_artifact_tag_markdown():
    assert wrap_artifact_tag("my-uuid-123", "markdown") == "<!-- sw-artifact: my-uuid-123 -->"


def test_wrap_artifact_tag_java():
    assert wrap_artifact_tag("my-uuid-123", "java") == "// sw-artifact: my-uuid-123"


def test_wrap_artifact_tag_sql():
    assert wrap_artifact_tag("my-uuid-123", "sql") == "-- sw-artifact: my-uuid-123"


def test_wrap_artifact_tag_json():
    # JSON doesn't support comments natively in SpecWeaver standards
    assert wrap_artifact_tag("my-uuid-123", "json") is None


def test_wrap_artifact_tag_unknown():
    assert wrap_artifact_tag("my-uuid-123", "cobol") is None

def test_extract_artifact_uuid_empty_and_none():
    assert extract_artifact_uuid("") is None
    assert extract_artifact_uuid(None) is None

def test_wrap_artifact_tag_empty_and_none():
    assert wrap_artifact_tag("", "python") is None
    assert wrap_artifact_tag(None, "python") is None

def test_wrap_artifact_tag_empty_language():
    assert wrap_artifact_tag("123", "") is None
    assert wrap_artifact_tag("123", None) is None  # type: ignore

def test_extract_artifact_uuid_multiple_tags():
    content = "# sw-artifact: 11111111-1111-1111-1111-111111111111\n# sw-artifact: 22222222-2222-2222-2222-222222222222"
    assert extract_artifact_uuid(content) == "11111111-1111-1111-1111-111111111111"

def test_extract_artifact_uuid_uppercase_uuid():
    content = "# sw-artifact: 123E4567-E89B-12D3-A456-426614174000"
    assert extract_artifact_uuid(content) == "123e4567-e89b-12d3-a456-426614174000"

def test_extract_artifact_uuid_no_space_after_colon():
    content = "# sw-artifact:123e4567-e89b-12d3-a456-426614174000"
    assert extract_artifact_uuid(content) == "123e4567-e89b-12d3-a456-426614174000"

def test_wrap_artifact_tag_uppercase_language():
    assert wrap_artifact_tag("my-uuid-123", "PYTHON") == "# sw-artifact: my-uuid-123"

