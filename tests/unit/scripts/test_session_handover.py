# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The handover generator: it owns the derivable half and must not touch the other one.

A handover holds two kinds of thing. State — suite numbers, gate status, open rows — which goes stale
because it is written by hand. And lossy facts — a decision waiting on a human, an approach measured
and rejected — which no artefact records unless someone writes them down at the moment.

This generator exists for the first kind only. **Every test here is really about the second**: the
value of regenerating state is nil if doing so can eat the paragraph that says "do not restart this
research". That paragraph is why `E-VAL-03` survived across sessions.
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


@pytest.fixture
def ho() -> ModuleType:
    """`scripts/` is not an importable package; load by path, as the sibling script tests do."""
    spec = importlib.util.spec_from_file_location(
        "session_handover", REPO_ROOT / "scripts" / "session_handover.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before exec: a `@dataclass` under `from __future__ import annotations` resolves its
    # fields through `sys.modules[cls.__module__]`, which is None for a module loaded purely by path.
    sys.modules["session_handover"] = module
    spec.loader.exec_module(module)
    return module


class TestSplice:
    """Replacing the generated block without disturbing anything a human wrote."""

    def test_human_sections_survive_regeneration(self, ho: ModuleType) -> None:
        """The whole point. Everything outside the markers is returned byte-for-byte."""
        existing = (
            "# Handover — 2026-01-01\n\n"
            f"{ho.BEGIN}\nold state, stale\n{ho.END}\n\n"
            "## Two decisions waiting\n\n"
            "1. `E-VAL-03` — read the analysis first. **Do not restart the research.**\n"
        )

        out = ho.splice(existing, "fresh state")

        assert "fresh state" in out
        assert "old state, stale" not in out
        assert "**Do not restart the research.**" in out
        assert "## Two decisions waiting" in out

    def test_a_file_with_no_markers_keeps_all_of_it(self, ho: ModuleType) -> None:
        """An older handover predating the generator must not be truncated into a state block."""
        existing = "# Handover\n\n## Decisions\n\nSomething only a human knew.\n"

        out = ho.splice(existing, "fresh state")

        assert "Something only a human knew." in out
        assert "fresh state" in out

    def test_inserting_the_block_preserves_every_other_line_exactly(self, ho: ModuleType) -> None:
        """Not "nothing important was lost" — every original line, in order, byte for byte.

        The weaker check passed while three blank lines were being injected at the seam. A property
        worth having is one worth asserting exactly.
        """
        existing = "# Handover\n\n## Decisions\n\nread the analysis first\n\n## Notes\n\nkeep\n"

        out = ho.splice(existing, "state")

        head, rest = out.split(ho.BEGIN, 1)
        _, tail = rest.split(ho.END, 1)
        outside = [ln for ln in (head + tail).splitlines() if ln.strip()]
        assert outside == [ln for ln in existing.splitlines() if ln.strip()]

    def test_an_unterminated_block_is_refused_not_guessed(self, ho: ModuleType) -> None:
        """A begin with no end means the file is damaged; writing over it would finish the job.

        Refusing costs a manual fix. Guessing where the block ends costs whatever was below it.
        """
        existing = f"# Handover\n\n{ho.BEGIN}\nhalf a block\n\n## Decisions\n\nkeep me\n"

        with pytest.raises(ho.HandoverError, match="unterminated"):
            ho.splice(existing, "fresh state")

    def test_regenerating_twice_changes_nothing_further(self, ho: ModuleType) -> None:
        """Idempotence — otherwise every run produces a diff and nobody trusts the file."""
        existing = f"# Handover\n\n{ho.BEGIN}\nold\n{ho.END}\n\n## Notes\n\nkeep\n"

        once = ho.splice(existing, "state")
        twice = ho.splice(once, "state")

        assert once == twice

    def test_the_marker_names_the_script_that_writes_it(self, ho: ModuleType) -> None:
        """The marker embeds this script's filename, so renaming the script breaks the file format.

        That is not hypothetical: the module was renamed and a later pass corrected the filename in
        its own docstring, silently rewriting the marker with it. Every existing handover then had a
        `begin` the script no longer recognised. `splice` refused rather than clobbering — the guard
        worked — but the failure was avoidable, and this is what makes it so.
        """
        assert Path(ho.__file__).name in ho.BEGIN, (
            f"the marker names a script that is not this one:\n{ho.BEGIN}"
        )


class TestDerivedCounts:
    """The numbers, read from fixture markdown rather than the live repo."""

    def test_migration_rows_are_counted_by_state(self, ho: ModuleType) -> None:
        text = (
            "## 🚚 Integration Migration (`-MIG`)\n\n"
            "| x | `✅` `INT-US-01-MIG` | US-1 | done | `A-SENS-01` |\n"
            "| x | `[ ]` `INT-US-02-MIG` | US-2 | open | `A-SENS-02` |\n"
            "| x | `🔵` `INT-US-03-MIG` | US-3 | held on `TECH-031` | `A-SENS-03` |\n"
            "\n## Next Section\n"
        )

        counts = ho.migration_counts(text)

        assert counts == {"discharged": 1, "open": 1, "held": 1}

    def test_open_contract_rows_exclude_the_runnable_ones(self, ho: ModuleType) -> None:
        """`Runnable today` is the discriminant, and only 6-column inventory rows are rows."""
        text = (
            "| # | Path | Span | Owner | Runnable today | Blocker |\n"
            "|---|---|---|---|---|---|\n"
            "| P-1 | done thing | single | `A-SENS-01` | yes — **done** | — |\n"
            "| P-2 | blocked thing | cross | `B-SENS-07` (unbuilt) | no | `B-SENS-07` |\n"
            "| P-3 | needs a test | cross | this contract | no | none — needs an e2e |\n"
        )

        rows = ho.open_rows(text, story="US-99")

        assert [r.number for r in rows] == ["P-2", "P-3"]
        assert rows[0].blocked_externally is True
        assert rows[1].blocked_externally is False, (
            "'none — ...' names no blocker, so it is actionable"
        )


class TestNeedsYou:
    """Separating what a human must answer from what any agent can just go and do.

    Eight open rows with no external blocker is a number. Three of them wanting a decision from the
    user and five wanting a test from whoever picks them up is an instruction. The generator can tell
    them apart because the blocker cell already says which it is.
    """

    def test_a_row_wanting_a_decision_is_routed_to_the_user(self, ho: ModuleType) -> None:
        rows = [
            ho.OpenRow("US-03", "P-6", "rule uri", "needs a scope decision — see below", False),
            ho.OpenRow("US-09", "P-2", "containers", "product decision", False),
            ho.OpenRow("US-08", "P-5", "wizard", "none — needs an e2e, not a feature", False),
            ho.OpenRow("US-20", "P-5", "inferred", "`B-SENS-07` — no resolver exists", True),
        ]

        assert [r.number for r in ho.awaiting_decision(rows)] == ["P-6", "P-2"]
        assert [r.number for r in ho.awaiting_work(rows)] == ["P-5"], (
            "a row blocked on named work is neither — it is waiting on someone else's build"
        )

    def test_the_section_says_so_when_it_cannot_know(self, ho: ModuleType) -> None:
        """HITL gates are not derivable. Silence must read as 'nothing was recorded', not 'nothing exists'."""
        block = ho.render_needs_you(unpushed=0, dirty=0, rows=[], handover_text="")

        assert "not derivable" in block.lower() or "recorded" in block.lower()

    def test_unpushed_work_names_the_command(self, ho: ModuleType) -> None:
        """`git push` is not in this repo's Bash allow-list, so it is always the user's to run."""
        block = ho.render_needs_you(unpushed=9, dirty=0, rows=[], handover_text="")

        assert "9" in block
        assert "git push" in block


class TestDegenerate:
    """A handover that has rotted must say so, because nothing else will look at it.

    Measured 2026-08-22: `.tmp/HANDOVER.md` held **23 MB across 332,068 lines with 122 distinct
    ones** — one section repeated roughly ten thousand times, some copies corrupted mid-line. It had
    been that way for an unknown number of sessions. `.tmp/` is gitignored, so no diff, no gate and
    no reader ever saw it, and the content it buried was months stale.

    `splice` was not the cause and this does not accuse it: verified on the real file, one marker
    pair and a re-run changing zero bytes. The point is that a file this tool writes on every commit
    boundary can rot underneath it in silence, and the tool is the only thing positioned to notice.
    """

    def test_a_normal_handover_is_not_flagged(self, ho: ModuleType) -> None:
        """The control, and the one that matters: a false alarm here trains people to ignore it."""
        text = "# Handover\n\n" + "\n".join(f"- a real and distinct line {i}" for i in range(200))

        assert ho.degenerate_reason(text) is None

    def test_a_short_repetitive_handover_is_not_flagged(self, ho: ModuleType) -> None:
        """Boundary: real handovers repeat themselves — blank lines, list markers, headings.

        Repetition only means rot at scale, so the guard must not fire on a small file that happens
        to say the same thing twice.
        """
        text = "# Handover\n\n" + "\n".join(["- the same line"] * 30)

        assert ho.degenerate_reason(text) is None

    def test_the_real_shape_that_rotted_is_flagged(self, ho: ModuleType) -> None:
        """Happy path for the guard: thousands of lines, almost none of them distinct."""
        section = ["## `TECH-068` — a section", "", "Some prose about it.", ""]
        text = "# Handover\n\n" + "\n".join(section * 3000)

        reason = ho.degenerate_reason(text)
        assert reason is not None
        assert "distinct" in reason

    def test_an_enormous_handover_is_flagged_even_if_every_line_differs(
        self, ho: ModuleType
    ) -> None:
        """Boundary: size alone is enough. Nobody reads a megabyte of handover, distinct or not."""
        text = "# Handover\n\n" + "\n".join(f"- distinct line number {i}" for i in range(60000))

        reason = ho.degenerate_reason(text)
        assert reason is not None
        assert "large" in reason.lower() or "bytes" in reason.lower()

    def test_an_empty_handover_is_not_flagged(self, ho: ModuleType) -> None:
        """Hostile: nothing to divide by. A ratio guard that raises on the empty case is a new bug."""
        assert ho.degenerate_reason("") is None
        assert ho.degenerate_reason("   \n\n  \n") is None

    def test_main_warns_rather_than_refusing_to_write(
        self,
        ho: ModuleType,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Graceful degradation: the warning must not cost the user the run.

        Blocking here would strand the boundary on a gitignored scratch file, which is worse than
        the rot. It reports and writes.
        """
        handover = tmp_path / "HANDOVER.md"
        handover.write_text("# Handover\n\n" + "\n".join(["## same"] * 12000), encoding="utf-8")
        monkeypatch.setattr(ho, "HANDOVER", handover)
        monkeypatch.setattr(ho, "render_state", lambda **_: "## State\n\n- nothing")

        code = ho.main([])

        assert code == 0
        assert "distinct" in capsys.readouterr().out
        assert "## State" in handover.read_text(encoding="utf-8")
