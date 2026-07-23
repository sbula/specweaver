# mypy: ignore-errors
"""INT-US-02 SF-03 (G-b): direct tests for the inline draft-chain report (FR-6).

The report had NO direct test — which is how the uppercase-"FAIL" comparison bug
survived SF-01 (RuleStatus.value is lowercase "fail"; the report compared against
"FAIL" and silently printed nothing). These tests pin the REAL production shapes:
lowercase rule statuses and finding dicts from ReviewFinding.model_dump().
"""

from io import StringIO
from pathlib import Path
from types import SimpleNamespace

from rich.console import Console

from specweaver.core.flow.engine.state import StepStatus
from specweaver.workflows.review.interfaces.cli import _report_draft_chain


def _record(step_name: str, status: StepStatus, output):
    return SimpleNamespace(step_name=step_name, status=status, result=SimpleNamespace(output=output))


def _run_report(monkeypatch, records) -> str:
    from specweaver.interfaces.cli import _core

    buf = StringIO()
    monkeypatch.setattr(_core, "console", Console(file=buf, force_terminal=False, width=200))
    run_state = SimpleNamespace(step_records=records)
    _report_draft_chain(run_state, Path("dummy_spec.md"))
    return buf.getvalue()


class TestReportDraftChain:
    def test_happy_path_all_green(self, monkeypatch, tmp_path: Path) -> None:
        out = _run_report(
            monkeypatch,
            [
                _record("draft_spec", StepStatus.PASSED, {"path": str(tmp_path / "s.md")}),
                _record(
                    "validate_spec", StepStatus.PASSED, {"total": 12, "passed": 12, "results": []}
                ),
                _record(
                    "review_spec",
                    StepStatus.PASSED,
                    {"verdict": "accepted", "findings_count": 0, "findings": []},
                ),
            ],
        )
        assert "Spec drafted:" in out
        assert "12/12 rules passed" in out
        assert "Review: accepted" in out
        assert "rejected" not in out

    def test_failed_rules_print_with_real_lowercase_status(self, monkeypatch) -> None:
        """The regression pin: production emits RuleStatus.value == "fail" (lowercase)."""
        out = _run_report(
            monkeypatch,
            [
                _record(
                    "validate_spec",
                    StepStatus.FAILED,
                    {
                        "total": 12,
                        "passed": 10,
                        "results": [
                            {"rule_id": "S01", "status": "fail", "message": "Missing DoD section"},
                            {"rule_id": "S02", "status": "pass", "message": ""},
                        ],
                    },
                ),
            ],
        )
        assert "10/12 rules passed" in out
        assert "S01" in out
        assert "Missing DoD section" in out
        assert "S02" not in out  # passing rules are not listed

    def test_rejected_review_prints_finding_messages_from_dicts(self, monkeypatch) -> None:
        """Findings are ReviewFinding.model_dump() dicts — the report must print the
        message text, never the raw dict repr."""
        out = _run_report(
            monkeypatch,
            [
                _record(
                    "review_spec",
                    StepStatus.FAILED,
                    {
                        "verdict": "denied",
                        "findings_count": 1,
                        "findings": [
                            {
                                "category": "clarity",
                                "message": "Section 2 is ambiguous",
                                "severity": "major",
                                "suggestion": "",
                                "confidence": 80,
                                "below_threshold": False,
                            }
                        ],
                    },
                ),
            ],
        )
        assert "Review: denied" in out
        assert "rejected" in out
        assert "Section 2 is ambiguous" in out
        assert "'category'" not in out  # no raw dict repr leaked

    def test_boundary_empty_step_records_prints_nothing(self, monkeypatch) -> None:
        assert _run_report(monkeypatch, []).strip() == ""

    def test_boundary_none_step_records_prints_nothing(self, monkeypatch) -> None:
        from specweaver.interfaces.cli import _core

        buf = StringIO()
        monkeypatch.setattr(_core, "console", Console(file=buf, force_terminal=False, width=200))
        _report_draft_chain(SimpleNamespace(step_records=None), Path("dummy_spec.md"))
        assert buf.getvalue().strip() == ""

    def test_hostile_malformed_outputs_do_not_crash(self, monkeypatch) -> None:
        """Non-dict outputs, non-dict rule entries, and plain-string findings all degrade
        gracefully (the report is a best-effort view, never a crash source)."""
        out = _run_report(
            monkeypatch,
            [
                _record("draft_spec", StepStatus.PASSED, "not-a-dict"),
                _record(
                    "validate_spec",
                    StepStatus.FAILED,
                    {"total": 1, "passed": 0, "results": ["garbage", None, 42]},
                ),
                _record(
                    "review_spec",
                    StepStatus.FAILED,
                    {"verdict": "denied", "findings": ["plain string finding", None]},
                ),
            ],
        )
        assert "0/1 rules passed" in out
        assert "plain string finding" in out

    def test_hostile_rich_markup_in_llm_text_does_not_crash(self, monkeypatch) -> None:
        """Red/Blue (SF-03): finding/rule text is LLM- or content-derived — an unmatched
        closing tag like [/notatag] raises rich.errors.MarkupError if printed unescaped,
        crashing the report AFTER the run succeeded."""
        out = _run_report(
            monkeypatch,
            [
                _record(
                    "validate_spec",
                    StepStatus.FAILED,
                    {
                        "total": 2,
                        "passed": 1,
                        "results": [
                            {
                                "rule_id": "S06",
                                "status": "fail",
                                "message": "Use [bold]X[/notatag] in section 2",
                            }
                        ],
                    },
                ),
                _record(
                    "review_spec",
                    StepStatus.FAILED,
                    {
                        "verdict": "denied",
                        "findings": [{"message": "Replace [foo] with [/bar] everywhere"}],
                    },
                ),
            ],
        )
        assert "Use [bold]X[/notatag] in section 2" in out
        assert "Replace [foo] with [/bar] everywhere" in out


class TestDisplayReviewResultHostileMarkup:
    """Red/Blue (SF-03, fix-inherited): `sw review`'s display has the same unescaped-LLM-text
    print paths (summary + finding messages)."""

    def test_hostile_markup_in_summary_and_findings_does_not_crash(self, monkeypatch) -> None:
        import typer

        from specweaver.interfaces.cli import _core
        from specweaver.workflows.review.interfaces.cli import _display_review_result
        from specweaver.workflows.review.reviewer import (
            ReviewFinding,
            ReviewResult,
            ReviewVerdict,
        )

        buf = StringIO()
        monkeypatch.setattr(_core, "console", Console(file=buf, force_terminal=False, width=200))
        result = ReviewResult(
            verdict=ReviewVerdict.DENIED,
            summary="Overall: fix [bold]this[/notatag] first",
            findings=[ReviewFinding(message="Drop the [/stray] closing tag", severity="major")],
        )
        import contextlib

        # DENIED exits 1 by contract — only MarkupError would be a failure here.
        with contextlib.suppress(typer.Exit):
            _display_review_result(result)
        out = buf.getvalue()
        assert "Overall: fix [bold]this[/notatag] first" in out
        assert "Drop the [/stray] closing tag" in out
