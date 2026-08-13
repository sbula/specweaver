# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What `Drafter` and `FeatureDrafter` share, and the three things that differ.

`TECH-037`. The two classes had **byte-identical** `__init__` (17 lines) and `_generate_section`
(35 lines), and a `draft` differing in exactly four places: the section list, the Jinja template,
the filename suffix, and the prose. Three of those are data; the fourth is a docstring.

So they are one drafter parameterised three ways, and this pins that — a future third drafter
should be three class attributes, not a third copy.
"""

from __future__ import annotations

from specweaver.workflows.drafting._base import BaseDrafter
from specweaver.workflows.drafting.drafter import Drafter
from specweaver.workflows.drafting.feature_drafter import FeatureDrafter

DRAFTERS = [Drafter, FeatureDrafter]


class TestBaseDrafter:
    def test_both_drafters_derive_from_it(self) -> None:
        for cls in DRAFTERS:
            assert issubclass(cls, BaseDrafter), f"{cls.__name__} does not share the base"

    def test_neither_redeclares_the_shared_methods(self) -> None:
        """17 + 35 identical lines became one copy; a regression would restore a per-class one."""
        for cls in DRAFTERS:
            for method in ("__init__", "_generate_section", "draft"):
                assert method not in vars(cls), f"{cls.__name__} re-declares {method}"

    def test_each_drafter_names_its_sections(self) -> None:
        assert Drafter.SECTIONS is not FeatureDrafter.SECTIONS
        for cls in DRAFTERS:
            assert cls.SECTIONS, f"{cls.__name__} has no sections"

    def test_each_drafter_names_its_template(self) -> None:
        assert Drafter.TEMPLATE is not FeatureDrafter.TEMPLATE

    def test_the_filename_suffix_is_what_distinguishes_the_artefacts(self) -> None:
        """`<name>_spec.md` vs `<name>_feature_spec.md`.

        Load-bearing, not cosmetic: `feature_name_from_spec` strips `_feature_spec` to recover the
        feature name, and `DraftSpecHandler`'s exists-skip keys on the component form.
        """
        assert Drafter.FILENAME_SUFFIX == "_spec.md"
        assert FeatureDrafter.FILENAME_SUFFIX == "_feature_spec.md"

    def test_the_two_suffixes_are_distinct(self) -> None:
        assert Drafter.FILENAME_SUFFIX != FeatureDrafter.FILENAME_SUFFIX

    def test_the_base_declares_no_sections_of_its_own(self) -> None:
        """The base is the mechanism; a subclass that forgets its data must not inherit someone's."""
        assert not BaseDrafter.SECTIONS
