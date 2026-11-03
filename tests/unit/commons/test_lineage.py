# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from specweaver.commons.lineage import (
    extract_artifact_uuid,
    tag_content,
    wrap_artifact_tag,
)

_UUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
_TAGGED_YAML = f"# sw-artifact: {_UUID}\nkey: value\n"


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


def test_wrap_artifact_tag_kotlin():
    """D-INTL-08 FR-4: a generated `.kt` file is tagged like Java."""
    assert wrap_artifact_tag("my-uuid-123", "kotlin") == "// sw-artifact: my-uuid-123"
    assert wrap_artifact_tag("my-uuid-123", "kt") == "// sw-artifact: my-uuid-123"


# --- tag_content ------------------------------------------------------------


def test_the_tag_is_prepended_in_the_language_s_comment_syntax() -> None:
    assert tag_content("key: value\n", _UUID, "yaml") == _TAGGED_YAML


def test_a_language_with_no_comment_syntax_is_left_alone() -> None:
    """`wrap_artifact_tag` returns None for json, and corrupting the file is worse than no tag."""
    assert tag_content('{"a": 1}', _UUID, "json") == '{"a": 1}'


def test_content_that_already_carries_the_tag_is_not_tagged_twice() -> None:
    assert tag_content(_TAGGED_YAML, _UUID, "yaml") == _TAGGED_YAML


def test_content_carrying_a_different_uuid_is_left_alone() -> None:
    """Two tags in one file is a lineage fork. The one already on disk wins."""
    other = f"# sw-artifact: {'a' * 8}-1111-2222-3333-{'b' * 12}\nkey: value\n"

    assert tag_content(other, _UUID, "yaml") == other
