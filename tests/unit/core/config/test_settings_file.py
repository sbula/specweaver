# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One reader turns settings text into a strict model or a located error.

Proves: TECH-076 FR-6, TECH-076 NFR-3

| Bucket | Case |
|---|---|
| Happy | a valid table becomes the model |
| Boundary | an absent table and an empty text give the model's defaults |
| Degradation | a syntax error names `(syntax)` and its real line, also where `lineno` is missing |
| Hostile | an unknown key is reported before a missing one; a value never reaches the message |
"""

from __future__ import annotations

import tomllib

import pytest
from pydantic import BaseModel, ConfigDict

from specweaver.core.config.doc_policy import parse_doc_policy
from specweaver.core.config.llm_settings_parse import parse_project_llm
from specweaver.core.config.settings_file import SettingsFileError, load_toml, parse_section


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "off"
    count: int = 1
    name: str = "x"


def test_a_valid_table_becomes_the_model() -> None:
    parsed = parse_section('[demo]\nmode = "on"\ncount = 3\n', "s.toml", "demo", _Section)

    assert (parsed.mode, parsed.count) == ("on", 3)


@pytest.mark.parametrize("text", ["", "[other]\nkey = 1\n"])
def test_an_absent_table_is_the_defaults(text: str) -> None:
    assert parse_section(text, "s.toml", "demo", _Section) == _Section()


def test_a_syntax_error_names_its_real_line() -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_section('[demo]\nmode = "on"\ncount = = 3\n', "s.toml", "demo", _Section)

    assert (caught.value.source, caught.value.key, caught.value.line) == ("s.toml", "(syntax)", 3)


def test_the_line_is_found_without_lineno(monkeypatch: pytest.MonkeyPatch) -> None:
    """Before Python 3.14 `TOMLDecodeError` has no `lineno`; the line is in the message."""
    real = tomllib.loads

    def old_python(text: str) -> object:
        try:
            return real(text)
        except tomllib.TOMLDecodeError as exc:
            stripped = tomllib.TOMLDecodeError(str(exc))
            for attribute in ("lineno", "colno", "doc", "pos", "msg"):
                stripped.__dict__.pop(attribute, None)
            raise stripped from None

    monkeypatch.setattr(tomllib, "loads", old_python)

    with pytest.raises(SettingsFileError) as caught:
        load_toml("a = 1\nb = 2\nc = = 3\n", "s.toml")

    assert caught.value.line == 3


def test_an_unknown_key_is_reported_before_a_missing_one() -> None:
    class _Needs(BaseModel):
        model_config = ConfigDict(extra="forbid")

        mode: str

    with pytest.raises(SettingsFileError) as caught:
        parse_section('[demo]\n\nmod = "on"\n', "s.toml", "demo", _Needs)

    assert (caught.value.key, caught.value.line) == ("demo.mod", 3)


def test_a_value_never_reaches_the_message() -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_section('[demo]\ncount = "sk-SECRET-123"\n', "s.toml", "demo", _Section)

    assert "sk-SECRET-123" not in str(caught.value)
    assert caught.value.key == "demo.count"
    assert caught.value.line == 2


def test_a_validator_message_carries_no_prefix() -> None:
    from pydantic import field_validator

    class _Checked(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str = "x"

        @field_validator("name")
        @classmethod
        def _short(cls, value: str) -> str:
            if len(value) > 3:
                raise ValueError("name is at most 3 characters")
            return value

    with pytest.raises(SettingsFileError) as caught:
        parse_section('[demo]\nname = "long"\n', "s.toml", "demo", _Checked)

    assert caught.value.message == "name is at most 3 characters"


_BROKEN = "[llm]\nschema_version = 1\n[docs]\nrule = = 1\n"


def test_every_reader_reports_a_syntax_error_alike() -> None:
    """[docs], [llm] and any other section read one text through one reader."""
    found = []
    for read in (
        lambda: parse_doc_policy(_BROKEN, "p.toml"),
        lambda: parse_project_llm(_BROKEN, "p.toml"),
        lambda: parse_section(_BROKEN, "p.toml", "demo", _Section),
    ):
        with pytest.raises(SettingsFileError) as caught:
            read()
        found.append((caught.value.key, caught.value.line, caught.value.message))

    assert found == [("(syntax)", 4, "not valid TOML")] * 3
