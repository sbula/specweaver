# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One Jinja environment and one markdown sanitiser for the UI.

`TECH-037`. `htmx.py` and `routes.py` each built their own `Jinja2Templates`, defined their own
`_render_markdown`, and registered it as their own `markdown` filter — the same thirty lines twice,
including the **bleach allowed-tags list**.

That list is a sanitiser allowlist, so two copies is the same hazard as the duplicated
`FolderGrant`: tightening one leaves the other permissive, and the copy an exploit reaches is
whichever module happens to render the page.
"""

from __future__ import annotations

from specweaver.interfaces.api.ui import _templates, htmx, routes


class TestRenderMarkdown:
    def test_the_rendering_module_uses_the_shared_environment(self) -> None:
        assert routes.templates is _templates.templates

    def test_htmx_builds_no_environment_of_its_own(self) -> None:
        """`htmx.py`'s copy was INERT and that is why it is gone.

        It constructed a `Jinja2Templates`, defined `_render_markdown`, and registered the filter
        on that environment — which nothing in the module ever rendered through. `routes.py` did
        the rendering, through its own separate environment. Thirty duplicated lines of sanitiser
        that never ran, and a second allowlist to keep in step for no benefit.
        """
        assert not hasattr(htmx, "templates")
        assert not hasattr(htmx, "_render_markdown")

    def test_the_markdown_filter_is_registered_on_the_shared_environment(self) -> None:
        assert _templates.templates.env.filters["markdown"] is _templates.render_markdown

    def test_empty_input_renders_nothing(self) -> None:
        assert _templates.render_markdown(None) == ""
        assert _templates.render_markdown("") == ""

    def test_ordinary_markdown_is_rendered(self) -> None:
        assert "<h1>" in _templates.render_markdown("# Title")

    def test_a_script_tag_is_stripped(self) -> None:
        """The reason this is sanitised at all: run output is LLM-authored and user-supplied."""
        out = _templates.render_markdown("hello <script>alert(1)</script>")

        assert "<script>" not in out
        assert "alert" not in out or "&lt;script&gt;" in out

    def test_an_event_handler_attribute_is_stripped(self) -> None:
        out = _templates.render_markdown('<div onclick="steal()">x</div>')

        assert "onclick" not in out

    def test_a_fenced_code_block_survives(self) -> None:
        """`fenced_code` is enabled, and `pre` is on the allowlist — both halves must hold."""
        out = _templates.render_markdown("```\nprint(1)\n```")

        assert "<pre>" in out

    def test_a_table_survives(self) -> None:
        out = _templates.render_markdown("| a | b |\n| - | - |\n| 1 | 2 |")

        assert "<table>" in out
