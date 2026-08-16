# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the retirement-target guard (`scripts/check_retirement_targets.py`).

`ADR-003` retires an integration add-on by promising its scope *"moves to `X`, which owns its own
integration and e2e proof as FRs"*. That promise is unsatisfiable when `X` is already delivered:
`finished-stories-immutable` forbids adding an FR to a closed story, so the scope lands nowhere and
no gate can see it — `check_fr_coverage.py` only judges FRs somebody wrote.

Every rule here is driven against a synthetic roadmap built to violate it and one built to satisfy
it, because on the repo as it stands the check reports nothing, and a broken guard looks exactly
like a passing one.

`scripts/` is not an importable package, so the module is loaded by path.

No `Proves:` tag: this guard enforces an architectural decision (`ADR-003`, 2026-08-16 addendum)
rather than a story's FR, and citing a ticket that does not exist would be worse than citing none.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def crt() -> ModuleType:
    return _load("check_retirement_targets")


MATRIX = """# Capability Matrix

| DAL | Validation |
|---|---|
| **DAL-D** | `✅ D-VAL-03`: Polyglot QARunner<br>`🔜 E-VAL-04`: Rubric Reviews<br>`🔴 D-INTL-07`: Interview |
"""

#: The shape the topic docs actually use: a `* **`ID`...` entry, then an indented `>` block.
BLOCKQUOTE_NOTE = """## Sub-Story Add-Ons

* **`INT-US-03-SF01` — Multi-Language Test Support:** *Pending Design.* Integrates `D-VAL-03`.

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `D-VAL-03`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.
"""

#: The shape `master_story_roadmap.md` uses: one line, no blockquote.
INLINE_NOTE = """*   `[ ]` **INT-US-99-SF01:** RETIRED by `ADR-003` — requirements move to `E-VAL-04`
"""


def _tree(root: Path, notes: dict[str, str]) -> Path:
    """Build a minimal `docs/roadmap/` holding a capability matrix and the given note files."""
    roadmap = root / "docs" / "roadmap"
    roadmap.mkdir(parents=True)
    (roadmap / "capability_matrix.md").write_text(MATRIX, encoding="utf-8")
    for rel, body in notes.items():
        path = roadmap / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return roadmap


class TestCapabilityStatus:
    """`capability_status` reads the matrix, which is authoritative for capability IDs."""

    def test_reads_the_glyph_that_precedes_the_id(self, crt: ModuleType, tmp_path: Path) -> None:
        roadmap = _tree(tmp_path, {})
        assert crt.capability_status(roadmap)["D-VAL-03"] == "✅"

    def test_unbuilt_glyphs_are_kept_verbatim(self, crt: ModuleType, tmp_path: Path) -> None:
        roadmap = _tree(tmp_path, {})
        status = crt.capability_status(roadmap)
        assert status["E-VAL-04"] == "🔜"
        assert status["D-INTL-07"] == "🔴"

    def test_a_missing_matrix_is_not_an_empty_matrix(self, crt: ModuleType, tmp_path: Path) -> None:
        """`TECH-032`: a checker that cannot find its subject must say so, never pass."""
        with pytest.raises(FileNotFoundError):
            crt.capability_status(tmp_path / "docs" / "roadmap")


class TestRetirementNotes:
    """`retirement_notes` finds both note shapes and reads the capabilities each moves to."""

    def test_finds_the_blockquote_shape_and_its_targets(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": BLOCKQUOTE_NOTE})
        notes = crt.retirement_notes(roadmap)
        assert len(notes) == 1
        assert notes[0].retired_id == "INT-US-03-SF01"
        assert notes[0].targets == ("D-VAL-03",)

    def test_the_owner_is_the_entry_bullet_not_the_nearest_mention(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """Scanning back for any id labels the note with whatever is mentioned in the prose above.

        Two live notes were labelled `INT-US-03` and `INT-US-25` — the base contracts — instead of
        the add-ons actually retired, which sends the reader to the wrong entry.
        """
        body = BLOCKQUOTE_NOTE.replace(
            "Integrates `D-VAL-03`.\n",
            'Integrates `D-VAL-03`.\n  Distinct from the base contract\'s "INT-US-03 SF-03".\n',
        )
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert crt.retirement_notes(roadmap)[0].retired_id == "INT-US-03-SF01"

    def test_finds_the_single_line_shape(self, crt: ModuleType, tmp_path: Path) -> None:
        roadmap = _tree(tmp_path, {"master_story_roadmap.md": INLINE_NOTE})
        notes = crt.retirement_notes(roadmap)
        assert len(notes) == 1
        assert notes[0].retired_id == "INT-US-99-SF01"
        assert notes[0].targets == ("E-VAL-04",)

    def test_the_adr_that_did_the_retiring_is_not_a_target(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """`ADR-003` appears in every note. Reading it as a capability would flag all of them."""
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": BLOCKQUOTE_NOTE})
        assert "ADR-003" not in crt.retirement_notes(roadmap)[0].targets

    def test_multiple_targets_in_one_note_are_all_read(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        body = BLOCKQUOTE_NOTE.replace(
            "it moves to `D-VAL-03`, which owns its own",
            "it moves to `D-VAL-03`, `E-VAL-04` and `D-INTL-07`, which own their own",
        )
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert crt.retirement_notes(roadmap)[0].targets == ("D-INTL-07", "D-VAL-03", "E-VAL-04")

    def test_prose_before_the_note_is_not_swept_into_it(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """The entry line above the note names the capability being integrated — not a target."""
        body = BLOCKQUOTE_NOTE.replace("Integrates `D-VAL-03`.", "Integrates `D-INTL-07`.")
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert crt.retirement_notes(roadmap)[0].targets == ("D-VAL-03",)

    def test_prose_after_the_moves_to_clause_is_not_swept_in(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """A note that explains WHY a delivered capability was dropped still mentions it.

        Reading every id in the block would make the correction itself the offence — the check
        would then be unfixable by writing the truth down, which is the one thing it should reward.
        """
        body = BLOCKQUOTE_NOTE.replace(
            "it moves to `D-VAL-03`, which owns its own",
            "it moves to `E-VAL-04`, which owns its own",
        ).replace(
            "integration and e2e proof as FRs rather than a separate add-on restating them.",
            "integration and e2e proof as FRs.\n  > Corrected: this note also named `D-VAL-03`,"
            " which is delivered and did not need to own anything.",
        )
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert crt.retirement_notes(roadmap)[0].targets == ("E-VAL-04",)

    def test_un_retired_is_not_a_retirement(self, crt: ModuleType, tmp_path: Path) -> None:
        """`UN-RETIRED` contains `RETIRED`. A substring match would judge the very entries whose
        retirement was withdrawn — and they name a delivered capability by definition."""
        body = BLOCKQUOTE_NOTE.replace("**RETIRED 2026-08-13", "**UN-RETIRED 2026-08-16")
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert crt.retirement_notes(roadmap) == []

    def test_the_single_line_shape_may_say_move_rather_than_moves(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """`master_story_roadmap.md` writes "requirements move to", the topic docs "it moves to"."""
        roadmap = _tree(tmp_path, {"master_story_roadmap.md": INLINE_NOTE})
        assert crt.retirement_notes(roadmap)[0].targets == ("E-VAL-04",)

    def test_the_ownership_phrasing_is_read_too(self, crt: ModuleType, tmp_path: Path) -> None:
        """Three roadmap notes say "integration owned by `X`" rather than "moves to `X`".

        Reading only one phrasing left those three resolving to no destination at all — the guard
        passed them silently, which is the failure mode it exists to prevent.
        """
        body = INLINE_NOTE.replace("requirements move to", "integration owned by")
        roadmap = _tree(tmp_path, {"master_story_roadmap.md": body})
        assert crt.retirement_notes(roadmap)[0].targets == ("E-VAL-04",)

    def test_the_ownership_sentence_is_read_too(self, crt: ModuleType, tmp_path: Path) -> None:
        """Three topic-doc notes say "What changed is the owner: `X` builds it"."""
        body = BLOCKQUOTE_NOTE.replace(
            "it moves to `D-VAL-03`, which owns its own",
            "what changed is the owner: `E-VAL-04` builds it and owns its own",
        )
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert crt.retirement_notes(roadmap)[0].targets == ("E-VAL-04",)

    def test_a_note_naming_no_destination_is_reported_as_such(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """Silence is not a pass. A note with nowhere to point is listed, not skipped."""
        body = INLINE_NOTE.replace(" — requirements move to `E-VAL-04`", "")
        roadmap = _tree(tmp_path, {"master_story_roadmap.md": body})
        notes = crt.retirement_notes(roadmap)
        assert len(notes) == 1
        assert notes[0].targets == ()

    def test_feature_design_docs_are_out_of_scope(self, crt: ModuleType, tmp_path: Path) -> None:
        """The guard judges the REGISTRY. A design doc records its own section's history — those
        headings name no destination because the roadmap line already carries it, and judging both
        would report one retirement twice while demanding the destination be written twice."""
        roadmap = _tree(tmp_path, {"features/INT-US-04/INT-US-04_design.md": BLOCKQUOTE_NOTE})
        assert crt.retirement_notes(roadmap) == []


class TestOffenders:
    """`offenders` is the rule itself: a delivered target means the scope landed nowhere."""

    def test_a_delivered_target_is_reported(self, crt: ModuleType, tmp_path: Path) -> None:
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": BLOCKQUOTE_NOTE})
        found = crt.offenders(roadmap)
        assert [(o.retired_id, o.target) for o in found] == [("INT-US-03-SF01", "D-VAL-03")]

    def test_an_unbuilt_target_is_not_reported(self, crt: ModuleType, tmp_path: Path) -> None:
        roadmap = _tree(tmp_path, {"master_story_roadmap.md": INLINE_NOTE})
        assert crt.offenders(roadmap) == []

    def test_a_target_absent_from_the_matrix_is_reported(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """An unresolvable target is a broken reference, not a silent pass."""
        body = BLOCKQUOTE_NOTE.replace("`D-VAL-03`, which owns", "`C-NOPE-99`, which owns")
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert [o.status for o in crt.offenders(roadmap)] == ["?"]

    def test_a_note_with_no_destination_at_all_is_an_offence(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """`INT-US-25-SF01` read *"it moves to the capability that builds it"* — naming nobody.

        That is the unfalsifiable prose `ADR-003` set out to delete, wearing the ADR's own name. A
        guard that judges only the notes it can parse would pass every note written this way, so
        the hole is closed here rather than counted.
        """
        body = BLOCKQUOTE_NOTE.replace("`D-VAL-03`, which owns", "the capability that builds it,")
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert [(o.target, o.status) for o in crt.offenders(roadmap)] == [("(none named)", "?")]

    def test_only_the_delivered_target_of_a_mixed_note_is_reported(
        self, crt: ModuleType, tmp_path: Path
    ) -> None:
        """`INT-US-01-SF02`'s real shape: two delivered members and one unbuilt blocker."""
        body = BLOCKQUOTE_NOTE.replace(
            "it moves to `D-VAL-03`, which owns its own",
            "it moves to `D-VAL-03` and `E-VAL-04`, which own their own",
        )
        roadmap = _tree(tmp_path, {"topics/US-03_integration.md": body})
        assert [o.target for o in crt.offenders(roadmap)] == ["D-VAL-03"]


class TestMain:
    """The CLI contract `quality.py doc` depends on: 0 clean, 1 offenders, 2 cannot run."""

    def test_exits_one_and_names_the_offender(
        self, crt: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _tree(tmp_path, {"topics/US-03_integration.md": BLOCKQUOTE_NOTE})
        assert crt.main(["--root", str(tmp_path)]) == 1
        out = capsys.readouterr().out
        assert "INT-US-03-SF01" in out
        assert "D-VAL-03" in out

    def test_exits_zero_when_every_target_is_unbuilt(self, crt: ModuleType, tmp_path: Path) -> None:
        _tree(tmp_path, {"master_story_roadmap.md": INLINE_NOTE})
        assert crt.main(["--root", str(tmp_path)]) == 0

    def test_exits_two_when_the_roadmap_is_missing(self, crt: ModuleType, tmp_path: Path) -> None:
        assert crt.main(["--root", str(tmp_path)]) == 2

    def test_the_live_repo_passes(self, crt: ModuleType) -> None:
        """The guard ships with the tree already clean — the one mis-retirement is re-homed."""
        assert crt.main([]) == 0
