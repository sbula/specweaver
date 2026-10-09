# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Markdown and SQL files give up their `@trace` tags like every other language.

Proves: D-SENS-03 FR-4, FR-5

| Bucket | Case |
|---|---|
| Happy | an HTML comment in Markdown, and a line or block comment in SQL, give their tags |
| Boundary | several tags in one comment; an empty file gives none |
| Degradation | a file with comments but no tag gives none |
| Hostile | a tag inside a Markdown code block or in SQL code text is not a tag |
"""

from __future__ import annotations

from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure

_MD = """# Title

<!-- @trace(FR-1, NFR-2) -->

Text.

```
<!-- @trace(FR-9) -->
```

<!-- just a note -->
"""

_SQL = """-- @trace(FR-2)
/* @trace(FR-3) */
CREATE TABLE t (note text DEFAULT '@trace(FR-9)');
-- just a note
"""


def test_markdown_tags_come_from_html_comments_only() -> None:
    assert MarkdownCodeStructure().extract_traceability_tags(_MD) == {"FR-1", "NFR-2"}


def test_sql_tags_come_from_line_and_block_comments_only() -> None:
    assert SqlCodeStructure().extract_traceability_tags(_SQL) == {"FR-2", "FR-3"}


def test_empty_files_have_no_tags() -> None:
    assert MarkdownCodeStructure().extract_traceability_tags("") == set()
    assert SqlCodeStructure().extract_traceability_tags("") == set()
