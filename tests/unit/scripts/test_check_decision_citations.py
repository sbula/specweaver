# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A design must account for every must-not-guess trigger, and say what a fired one settled.

`PRINCIPLES.md` §2 lists the decisions an agent may not take alone. Nothing read a design against
that list, so the list was advisory: an agent could settle a spend ceiling, a
retention period or a proven-verdict, write it into a design, and pass every gate in the repo.

The check is a ratchet over designs that do not account for the list. Four rules decide what counts,
and each is proved below:

- the trigger list is READ from `PRINCIPLES.md`, never restated here — one fact, one place;
- a design must mention every trigger, so naming one and stopping does not pass;
- a trigger marked `fired` must also carry what was settled, so the section is evidence;
- a mention the parser cannot read counts as missing, so an unreadable design goes red rather than
  quiet.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from scripts.check_decision_citations import (
    audit_design,
    over_baseline,
    triggers_from_principles,
)

if TYPE_CHECKING:
    from pathlib import Path

PRINCIPLES = """
## 2. What is never yours to decide

| Group | Trigger | Fires on |
|---|---|---|
| Cost and exposure | `T-SPEND` | A number that turns into a bill |
| | `T-BOUNDARY` | Anything untrusted code can reach |
| The agreement | `T-PROVEN` | Calling something proven |

## 3. Test first, and let it fail

Nothing here is a trigger. `T-NOTATRIGGER` sits outside the table.
"""

TRIGGERS = frozenset({"T-SPEND", "T-BOUNDARY", "T-PROVEN"})


def _design(body: str) -> str:
    return (
        f"# D-EXAMPLE-01\n\n## Decisions taken with the user\n\n{body}\n\n## Scope\n\nUnrelated.\n"
    )


class TestTriggersFromPrinciples:
    def test_every_trigger_in_the_table_is_found(self) -> None:
        assert triggers_from_principles(PRINCIPLES) == TRIGGERS

    def test_an_id_outside_the_table_is_not_a_trigger(self) -> None:
        assert "T-NOTATRIGGER" not in triggers_from_principles(PRINCIPLES)

    def test_the_real_principles_file_parses(self) -> None:
        from scripts.check_decision_citations import PRINCIPLES_PATH

        found = triggers_from_principles(PRINCIPLES_PATH.read_text(encoding="utf-8"))
        assert "T-PROVEN" in found
        assert "T-SPEND" in found


class TestAuditDesign:
    def test_no_section_at_all_is_unaccounted(self) -> None:
        reasons = audit_design("# D-EXAMPLE-01\n\n## Scope\n\nNothing.\n", TRIGGERS)
        assert reasons
        assert "no `Decisions taken with the user` section" in reasons[0]

    def test_every_trigger_untouched_is_clean(self) -> None:
        text = _design("- `T-SPEND`, `T-BOUNDARY`, `T-PROVEN`: not touched")
        assert audit_design(text, TRIGGERS) == ()

    def test_naming_one_trigger_and_stopping_does_not_pass(self) -> None:
        text = _design("- `T-SPEND`: not touched")
        reasons = audit_design(text, TRIGGERS)
        assert any("T-BOUNDARY" in r for r in reasons)
        assert any("T-PROVEN" in r for r in reasons)

    def test_a_trigger_named_outside_the_section_does_not_count(self) -> None:
        text = (
            "# D-EXAMPLE-01\n\n## Decisions taken with the user\n\n"
            "- `T-SPEND`: not touched\n\n## Scope\n\n`T-BOUNDARY` `T-PROVEN` mentioned here.\n"
        )
        reasons = audit_design(text, TRIGGERS)
        assert any("T-BOUNDARY" in r for r in reasons)


class TestAuditDesignOnFiredTriggers:
    def test_fired_with_what_was_settled_is_clean(self) -> None:
        text = _design(
            "- `T-BOUNDARY`, `T-PROVEN`: not touched\n"
            "- `T-SPEND`: fired — ceiling set to $25 by the user"
        )
        assert audit_design(text, TRIGGERS) == ()

    def test_fired_with_nothing_after_it_is_unaccounted(self) -> None:
        text = _design("- `T-BOUNDARY`, `T-PROVEN`: not touched\n- `T-SPEND`: fired")
        reasons = audit_design(text, TRIGGERS)
        assert any("T-SPEND" in r and "fired" in r for r in reasons)

    def test_fired_with_only_a_dash_after_it_is_unaccounted(self) -> None:
        text = _design("- `T-BOUNDARY`, `T-PROVEN`: not touched\n- `T-SPEND`: fired —")
        assert audit_design(text, TRIGGERS)


class TestAuditDesignOnUnreadableLines:
    def test_a_trigger_with_no_marker_is_unaccounted(self) -> None:
        text = _design("- `T-BOUNDARY`, `T-PROVEN`: not touched\n- `T-SPEND` we discussed this")
        reasons = audit_design(text, TRIGGERS)
        assert any("T-SPEND" in r for r in reasons)

    def test_a_trigger_gets_one_reason_not_two(self) -> None:
        text = _design("- `T-BOUNDARY`, `T-PROVEN`: not touched\n- `T-SPEND` we discussed this")
        reasons = audit_design(text, TRIGGERS)
        assert len([r for r in reasons if "T-SPEND" in r]) == 1


class TestAuditDesignAtTheBoundaries:
    def test_an_empty_section_names_every_trigger(self) -> None:
        reasons = audit_design(_design(""), TRIGGERS)
        assert {"T-SPEND", "T-BOUNDARY", "T-PROVEN"} == {r.split(":")[0] for r in reasons}

    def test_a_subsection_does_not_end_the_section_early(self) -> None:
        text = (
            "# D-EXAMPLE-01\n\n## Decisions taken with the user\n\n"
            "- `T-SPEND`: not touched\n\n### Notes\n\n"
            "- `T-BOUNDARY`, `T-PROVEN`: not touched\n\n## Scope\n\nUnrelated.\n"
        )
        assert audit_design(text, TRIGGERS) == ()

    def test_a_trigger_without_backticks_does_not_count(self) -> None:
        text = _design("- T-SPEND, T-BOUNDARY, T-PROVEN: not touched")
        assert len(audit_design(text, TRIGGERS)) == 3

    def test_a_design_with_no_triggers_to_check_is_clean(self) -> None:
        assert audit_design(_design(""), frozenset()) == ()


class TestOverBaseline:
    def test_the_count_may_hold(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.json"
        baseline.write_text(json.dumps({"unaccounted": 137}), encoding="utf-8")
        assert over_baseline(137, baseline) is False

    def test_the_count_may_fall(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.json"
        baseline.write_text(json.dumps({"unaccounted": 137}), encoding="utf-8")
        assert over_baseline(4, baseline) is False

    def test_the_count_may_not_rise(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.json"
        baseline.write_text(json.dumps({"unaccounted": 137}), encoding="utf-8")
        assert over_baseline(138, baseline) is True

    def test_a_missing_baseline_fails_closed(self, tmp_path: Path) -> None:
        assert over_baseline(0, tmp_path / "absent.json") is True

    def test_an_unreadable_baseline_fails_closed(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.json"
        baseline.write_text("not json", encoding="utf-8")
        assert over_baseline(0, baseline) is True


@pytest.mark.parametrize("marker", ["not touched", "NOT TOUCHED", "Not Touched"])
def test_the_marker_is_case_insensitive(marker: str) -> None:
    text = _design(f"- `T-SPEND`, `T-BOUNDARY`, `T-PROVEN`: {marker}")
    assert audit_design(text, TRIGGERS) == ()
