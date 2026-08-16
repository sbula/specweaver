# Design: `sw usage --since` Crashes on Unparseable Input

- **Feature ID**: TECH-052
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: 2026-08-16, `INT-US-16` CB-1, while building the adversarial test matrix's
  hostile-input bucket for the telemetry read path.

## Problem Statement

`sw usage --since not-a-date` exits 1 with an **unhandled `ValueError`** — the user gets a Python
traceback instead of an error message.

```python
# src/specweaver/infrastructure/llm/interfaces/cli.py:161
parsed_since = datetime.fromisoformat(since) if since else None
```

There is no guard. `--since` is a free-text option (`--since` help: *"Filter records after this ISO
timestamp"*), so any typo — `2026-8-1`, `yesterday`, a pasted log line — produces a traceback.
Probed and confirmed 2026-08-16: exit code 1, `res.exception` is `ValueError`.

This matters slightly more than a cosmetic CLI defect because of where it sits. `sw usage` is the
**read half of the US-16 cost-visibility journey**: it is the surface a user reaches for when asking
what a run cost. A traceback there reads as "the telemetry is broken", not "the date was wrong".

Every other failure mode on this command is handled deliberately — no active project prints
`[yellow]No active project.[/yellow] Use [bold]sw use <name>[/bold] or pass [bold]--all[/bold].`
(`cli.py:150-156`), and an empty table prints `No usage data recorded`. `--since` is the one input
on the command that was never given the same treatment.

## Goal

A bad `--since` value produces a one-line error naming the expected format and a non-zero exit —
the same shape as the command's other two handled cases — and never a traceback.

## Relationship

- **`INT-US-16`** owns the cost-visibility journey and found this, but its three FRs are about
  whether a run's spend is **recorded and visible**. `--since` parsing is neither, so absorbing it
  into an approved contract would have widened it silently.
- **Delivered code.** `sw usage` ships as part of US-16's MVS, so by the ticket rule a defect in it
  becomes a new ticket rather than an edit to a delivered story's entry.
- Any sibling command taking a free-text timestamp should be checked at design time; this stub does
  not assume there are none.

## Candidate Approaches (not yet designed)

1. **Catch `ValueError` at the call site** and re-raise as a `typer.BadParameter` / styled console
   error. Smallest possible change, one call site.
2. **A Typer parameter callback** that validates and converts `--since` before the command body
   runs, so the error is reported by the CLI framework in its standard form alongside every other
   parameter error. Slightly more code; consistent with how Typer expects validation to be done, and
   it puts the format hint in `--help`.
3. **Accept more than ISO-8601** — relative forms like `7d` or `yesterday`. A feature, not a fix;
   listed only to be explicitly deferred.

## Non-Goals (proposed, pending design)

- Broadening what `--since` accepts (approach 3). The bug is the traceback, not the strictness.
- Auditing every CLI option in the repo for the same class of defect. If the design finds a second
  instance while checking siblings, that is a finding worth recording — but the sweep is its own
  ticket, not this one.
- Anything about what `sw usage` displays, which is `INT-US-16`'s business.

## Next Step

Run `specweaver-design TECH-052` — or, given the size, fold it into the next commit that touches
`llm/interfaces/cli.py` with a test that pins the exit code and the absence of a traceback. The
design decision is only approach 1 vs 2, and it is worth taking deliberately because 2 changes what
`--help` says.
