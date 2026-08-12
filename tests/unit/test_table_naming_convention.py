# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every database table carries its bounded context in its name, and nothing still uses the old ones.

Two halves of one convention. The declarative models must *declare* prefixed names, and no raw SQL
may still *reference* an unprefixed one — a rename that updated the models but missed a hand-written
query would leave the first half true and the second false, and only the second one breaks at
runtime.

**Why this is its own module.** The citation scan credits a story every requirement token in a file
that names it. Three existing test modules already name this story while proving a different
requirement about raw-sqlite3 tables; adding these tokens there would be true by the scan and
misleading to a reader. This module names one story, holds exactly the two tokens it earns, and
`test_this_module_carries_only_the_tokens_it_earns` pins that.

Proves: TECH-005 FR-4.
Proves: TECH-005 FR-5.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "specweaver"


#: Requirement ids are assembled rather than written out — a literal one here would be counted by
#: the very scan this module is careful about. The two in the docstring above are the only literals.
def _token(n: int) -> str:
    return f"FR-{n}"


#: The bounded-context prefixes a table name may start with. `memory_` is `workspace.memory`'s,
#: which shares `workspace`'s declarative base.
CONTEXT_PREFIXES = ("llm_", "workspace_", "memory_", "flow_", "graph_")

#: The pre-rename names. A reference to any of these in raw SQL means something was missed.
LEGACY_TABLE_NAMES = (
    "projects",
    "active_state",
    "project_standards",
    "artifact_events",
    "project_llm_links",
)

#: SQL keywords after which a bare identifier is a table reference.
_SQL_TABLE_CONTEXT = re.compile(
    r"\b(?:FROM|INTO|UPDATE|JOIN|TABLE)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE
)


def _declarative_bases() -> dict[str, object]:
    from specweaver.core.flow.store import Base as FlowBase
    from specweaver.infrastructure.llm.store import Base as LlmBase
    from specweaver.workspace.memory.store import Base as MemoryBase
    from specweaver.workspace.store import Base as WorkspaceBase

    return {
        "llm": LlmBase,
        "workspace": WorkspaceBase,
        "flow": FlowBase,
        "memory": MemoryBase,
    }


def unprefixed_tables(bases: dict[str, object]) -> list[str]:
    """Table names that do not start with a bounded-context prefix."""
    found: list[str] = []
    for context, base in bases.items():
        for table in sorted(base.metadata.tables):  # type: ignore[attr-defined]
            if not table.startswith(CONTEXT_PREFIXES):
                found.append(f"{context}: {table}")
    return found


def legacy_table_references(root: Path) -> list[str]:
    """Raw-SQL references to a pre-rename table name, under `root`.

    Matches the **identifier** after a SQL keyword rather than searching for the name as a
    substring. That distinction is the whole check: `workspace_projects` contains `projects`, so a
    substring search reports the corrected name as a violation and fails against a correct tree.

    An unreadable module raises rather than being skipped — skipping is how an absence proof goes
    quietly vacuous — with the path in the message, because a bare decoding error sends the reader
    to the wrong place.
    """
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as exc:
            msg = f"{path.name}: cannot read ({exc})"
            raise UnicodeDecodeError("utf-8", b"", 0, 1, msg) from exc
        found.extend(
            f"{path.name}: {ident}"
            for ident in _SQL_TABLE_CONTEXT.findall(text)
            if ident.lower() in LEGACY_TABLE_NAMES
        )
    return found


# ---------------------------------------------------------------------------
# The guard that stops both invariants being ornaments
# ---------------------------------------------------------------------------


def test_the_declarative_bases_register_tables() -> None:
    """Both invariants are absence-shaped, and absence is what an empty registry returns.

    A base that imported without registering anything — a moved model module, a renamed package —
    would satisfy the prefix invariant trivially while proving nothing. The sibling architecture
    modules each carry a guard of this shape; it is not inherited, so this one earns its own.
    """
    bases = _declarative_bases()

    assert set(bases) == {"llm", "workspace", "flow", "memory"}
    for context, base in bases.items():
        assert base.metadata.tables, f"{context} base registers no tables — the scan is vacuous"  # type: ignore[attr-defined]
    assert SRC_ROOT.is_dir(), "source root missing — the raw-SQL scan inspects nothing"
    assert list(SRC_ROOT.rglob("*.py")), "source root holds no modules"


# ---------------------------------------------------------------------------
# The two live invariants
# ---------------------------------------------------------------------------


def test_every_model_table_carries_its_bounded_context() -> None:
    """No `__tablename__` is left unprefixed once the rename has landed."""
    assert unprefixed_tables(_declarative_bases()) == []


def test_no_raw_sql_references_a_pre_rename_table_name() -> None:
    """The models were renamed and so was every hand-written query that named them.

    This is the half that breaks at runtime rather than at import: a missed string in raw SQL keeps
    working right up until the statement executes against a table that no longer exists.
    """
    assert legacy_table_references(SRC_ROOT) == []


# ---------------------------------------------------------------------------
# Synthetic probes — these prove the LOGIC and touch no real tree
# ---------------------------------------------------------------------------


class _FakeMeta:
    def __init__(self, tables: dict[str, object]) -> None:
        self.tables = tables


class _FakeBase:
    def __init__(self, *names: str) -> None:
        self.metadata = _FakeMeta(dict.fromkeys(names))


def test_an_unprefixed_table_name_is_reported() -> None:
    """Hostile: the check reports a violation rather than passing everything."""
    bases = {"workspace": _FakeBase("workspace_projects", "projects")}

    assert unprefixed_tables(bases) == ["workspace: projects"]  # type: ignore[dict-item]


def test_a_legacy_name_in_raw_sql_is_reported(tmp_path: Path) -> None:
    """Hostile: a hand-written query still naming a pre-rename table is found."""
    (tmp_path / "store.py").write_text('cur.execute("SELECT id FROM projects WHERE x = 1")\n')

    assert legacy_table_references(tmp_path) == ["store.py: projects"]


def test_a_reference_split_across_lines_is_reported(tmp_path: Path) -> None:
    """Hostile: real query strings wrap, and the keyword often ends up on its own line.

    This is the likeliest shape of a genuinely missed reference — a long statement formatted for
    readability. The pattern's `\\s+` spans newlines, but nothing proved it until now, so a later
    tightening to `[ \\t]+` would silently stop finding exactly the case most likely to occur.
    """
    (tmp_path / "store.py").write_text(
        'cur.execute(\n    """\n    SELECT id, name\n    FROM\n        projects\n'
        '    WHERE id = ?\n    """\n)\n'
    )

    assert legacy_table_references(tmp_path) == ["store.py: projects"]


def test_lowercase_sql_is_reported(tmp_path: Path) -> None:
    """Hostile: SQL keywords are not reliably uppercase in hand-written queries.

    Both other hostile probes use uppercase, so the `re.IGNORECASE` flag was load-bearing and
    untested — dropping it would have kept every existing test green while missing half the corpus.
    """
    (tmp_path / "store.py").write_text('cur.execute("select id from projects")\n')

    assert legacy_table_references(tmp_path) == ["store.py: projects"]


def test_a_prefixed_name_containing_a_legacy_substring_is_not_reported(tmp_path: Path) -> None:
    """Boundary: `workspace_projects` contains `projects` and is the CORRECT name.

    The trap this check exists to avoid. A substring search reports the fixed name as a violation,
    which would make the invariant above fail against a tree that is entirely correct — and the
    obvious "fix" would be to weaken the assertion.
    """
    (tmp_path / "store.py").write_text(
        'cur.execute("SELECT id FROM workspace_projects")\n'
        'cur.execute("UPDATE workspace_active_state SET x = 1")\n'
        'cur.execute("INSERT INTO llm_project_links VALUES (1)")\n'
    )

    assert legacy_table_references(tmp_path) == []


def test_the_keyword_context_is_required(tmp_path: Path) -> None:
    """Boundary: the word `projects` in prose or a variable name is not a table reference."""
    (tmp_path / "notes.py").write_text("# the projects table was renamed\nprojects = load()\n")

    assert legacy_table_references(tmp_path) == []


def test_an_unreadable_module_raises_instead_of_being_skipped(tmp_path: Path) -> None:
    """Degradation: a module the scan cannot read must not be treated as clean."""
    (tmp_path / "binary.py").write_bytes(b"\xff\xfe SELECT id FROM projects\n")

    with pytest.raises(UnicodeDecodeError, match=r"binary\.py"):
        legacy_table_references(tmp_path)


# ---------------------------------------------------------------------------
# This module guards its own citation footprint
# ---------------------------------------------------------------------------


def test_this_module_carries_only_the_tokens_it_earns() -> None:
    """One story, exactly two requirement tokens.

    A later contributor mentioning a third requirement in a comment, or naming a second story while
    explaining something, would silently credit work nobody did. The sibling module for the other
    ledger failed this assertion twice while being written, both times for real reasons.
    """
    source = Path(__file__).read_text(encoding="utf-8")

    tokens = re.findall(r"FR-\d+", source)
    assert sorted(set(tokens)) == [_token(4), _token(5)], f"unexpected tokens: {tokens}"
    assert len(tokens) == 2, f"expected exactly two tokens, found {len(tokens)}: {tokens}"

    stories = set(re.findall(r"\b(?:TECH|INT-US)-\d+\b", source))
    assert stories == {"TECH-005"}, f"this file must name one story only, found: {stories}"
