# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Go reports what a type is built from.

Proves: TECH-068 FR-4

Go shipped `TYPE_DECLARATION_NODES = ()`, so `extract_supertypes` returned `{}` before doing
anything — and the contract test looped over that empty dict, running its body zero times, so the
gap read as a pass. `FR-4` names no language exemption and the design's Non-Goals do not mention Go.

**Embedding is reported as extension**, settled with the user on 2026-08-22 against a tenth
`EdgeKind`. Go embedding is composition with method promotion rather than inheritance, and Go
people will say so — but the ontology defines extension as "A is built from B", which is exactly
what embedding does, and a new kind is a change every reader inherits.

**`implements` is empty for Go and always will be.** Interface satisfaction in Go is structural and
implicit: there is no syntax for it, so no AST can express it. That is a fact about the language,
not a gap in this parser.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure


@pytest.fixture(scope="module")
def go() -> GoCodeStructure:
    return GoCodeStructure()


class TestGoCodeStructureEmbedding:
    def test_an_embedded_struct_is_an_extension(self, go: GoCodeStructure) -> None:
        """Happy path: the promoted-method relationship a hierarchy traversal is asking about."""
        code = "package m\ntype Impl struct {\n\tBase\n\tY int\n}\n"

        assert go.extract_supertypes(code)["Impl"]["extends"] == ["Base"]

    def test_an_embedded_interface_is_an_extension(self, go: GoCodeStructure) -> None:
        """Happy path: the other half. Interface embedding really is set inclusion."""
        code = "package m\ntype ReadWriter interface {\n\tReader\n\tWrite()\n}\n"

        assert go.extract_supertypes(code)["ReadWriter"]["extends"] == ["Reader"]

    def test_a_named_field_is_not_a_supertype(self, go: GoCodeStructure) -> None:
        """Boundary: the whole distinction. An embed has NO field name; `Y int` has one.

        Without this the parser would report every field's type as a supertype, and a struct with
        five `int` fields would claim to extend `int` five times.
        """
        code = "package m\ntype Plain struct {\n\tY int\n\tName string\n}\n"

        assert go.extract_supertypes(code)["Plain"]["extends"] == []

    def test_a_method_is_not_a_supertype(self, go: GoCodeStructure) -> None:
        """Boundary: an interface's own methods are not types it embeds."""
        code = "package m\ntype Reader interface {\n\tRead() error\n}\n"

        assert go.extract_supertypes(code)["Reader"]["extends"] == []

    def test_a_pointer_embed_names_the_type_it_points_at(self, go: GoCodeStructure) -> None:
        """Boundary: `*Base` embeds `Base`. The star is not part of the name."""
        code = "package m\ntype Impl struct {\n\t*Base\n}\n"

        assert go.extract_supertypes(code)["Impl"]["extends"] == ["Base"]

    def test_a_qualified_embed_names_the_type_not_the_package(self, go: GoCodeStructure) -> None:
        """Boundary: `io.Reader` embeds `Reader` from `io` — the type is the last segment.

        Resolution indexes bare declared names, so a package-qualified string could never match one
        and would ghost even when the type IS in the parsed set.
        """
        code = "package m\ntype Impl struct {\n\tio.Reader\n}\n"

        assert go.extract_supertypes(code)["Impl"]["extends"] == ["Reader"]

    def test_several_embeds_are_all_reported(self, go: GoCodeStructure) -> None:
        """Boundary: Go allows more than one, and order is the source's."""
        code = "package m\ntype Impl struct {\n\tBase\n\tOther\n\tY int\n}\n"

        assert go.extract_supertypes(code)["Impl"]["extends"] == ["Base", "Other"]


class TestGoCodeStructureHasNoImplements:
    def test_implements_is_empty_for_a_struct(self, go: GoCodeStructure) -> None:
        """Boundary, and a statement about the language rather than about this code."""
        code = "package m\ntype Impl struct {\n\tBase\n}\n"

        assert go.extract_supertypes(code)["Impl"]["implements"] == []

    def test_satisfying_an_interface_produces_nothing(self, go: GoCodeStructure) -> None:
        """Boundary: `Impl` satisfies `Reader` here and no syntax anywhere says so.

        This is the test that stops somebody 'fixing' the empty list later: the relationship is
        real, the AST cannot see it, and inventing it would be a guess.
        """
        code = (
            "package m\n"
            "type Reader interface { Read() error }\n"
            "type Impl struct{}\n"
            "func (i Impl) Read() error { return nil }\n"
        )

        assert go.extract_supertypes(code)["Impl"]["implements"] == []


class TestGoCodeStructureDegradation:
    def test_every_declared_type_appears_even_with_no_supertype(self, go: GoCodeStructure) -> None:
        """Boundary: a type with nothing above it is still a type.

        The adapter uses these keys to tell a type from a procedure, so a struct that reports
        nothing must still report ITSELF — otherwise Go types stay classified as procedures and can
        never be the target of anyone's supertype edge.
        """
        code = "package m\ntype Alone struct{}\ntype Named interface{}\n"

        assert set(go.extract_supertypes(code)) == {"Alone", "Named"}

    def test_source_that_does_not_parse_reports_nothing(self, go: GoCodeStructure) -> None:
        """Graceful degradation: one bad file must not take a build down."""
        assert go.extract_supertypes("package ((( not go at all") == {}

    def test_empty_source_reports_nothing(self, go: GoCodeStructure) -> None:
        """Boundary: nothing in it is a real state."""
        assert go.extract_supertypes("") == {}

    def test_hostile_input_does_not_raise(self, go: GoCodeStructure) -> None:
        """Hostile: text that is not Go and never claimed to be."""
        assert isinstance(go.extract_supertypes("\x00\x01 ../../etc/passwd {{{"), dict)
