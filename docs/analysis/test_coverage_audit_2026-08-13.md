# Test-coverage audit — every capability and contract, 2026-08-13

One mechanical pass over `docs/roadmap/features/**` and the 28 integration contracts, asking a
single question per item: **can the implementation be shown to meet the specification?**

> [!IMPORTANT]
> **What this measures, and what it does not.** Every number below is about **attribution and
> existence** — does the design state requirements, is each carried by a plan, is each cited by a
> test. It says nothing about whether those tests are any good. A test that asserts nothing counts
> as a citation here. Strength is only answerable by mutation testing (`A-VAL-03`); see
> `closure-contract.md`. So this is a list of **open points to check**, not a list of proven gaps.

## Correction, same day

**The first version of this document overstated category B by roughly ten times**, and the
correction is worth more than the original number.

It counted 31 delivered items with "no FR table". **26 of those are `TECH` tickets, which
legitimately have none** — the `specweaver-ticket` stub is Problem Statement / Candidate Approaches
/ Non-Goals, with no requirements table, because a defect report is not a feature specification.
Only the `specweaver-design` skill mandates Functional Requirements (its phase-3 Section A).

Counting capabilities alone, the real numbers are below. The error came from treating every
directory under `features/` as the same kind of thing, which is the same mistake as reading a
directory listing for a layer model — measure the population before measuring the property.

## Headline

**82 items are marked delivered, of which 47 are capabilities and 35 are `TECH` tickets.**

| Delivered **capabilities** (47) | Count |
|---|---|
| A — FR gate `BLOCKED`: requirements stated, not all planned or tested | **40** |
| B — the gate cannot run at all | **5** |
| C — clean | **2** |

| Delivered **`TECH` tickets** (35) | Count |
|---|---|
| FR gate `BLOCKED` | 3 |
| no FR table — **expected**, the ticket stub has none | 26 |
| clean | 6 |

Category A alone accounts for **266 declared FRs**, of which **133** are carried by no
implementation plan and **241** are cited by no test file.

## A — delivered, requirements stated, coverage incomplete (43: 40 capabilities + 3 TECH)

The gate runs and fails. Each has a concrete, per-FR answer already available from
`python scripts/check_fr_coverage.py <ID>`.

- **01 ui glass** — `E-UI-01` (7/7 FRs untested)
- **02 sensors** — `A-SENS-01` (3/3 FRs untested), `B-SENS-01` (6/6 FRs untested), `B-SENS-02` (5/5 FRs untested), `D-SENS-02` (7/7 FRs untested)
- **03 flow engine** — `B-FLOW-01` (9/9 FRs untested), `C-FLOW-02` (5/5 FRs untested), `C-FLOW-03`
  (6/6 FRs untested), `C-FLOW-05` (2/2 FRs untested), `D-FLOW-03` (7/7 FRs untested), `D-FLOW-04`
  (6/6 FRs untested), `E-FLOW-03` (7/7 FRs untested)
- **04 intelligence** — `B-INTL-02` (5/5 FRs untested), `B-INTL-09` (9/9 FRs untested), `C-INTL-01`
  (5/5 FRs untested), `C-INTL-02` (4/4 FRs untested), `C-INTL-05` (9/9 FRs untested), `D-INTL-01`
  (3/3 FRs untested), `D-INTL-05` (3/3 FRs untested), `D-INTL-06` (9/9 FRs untested), `E-INTL-01`
  (3/3 FRs untested), `E-INTL-02` (3/3 FRs untested)
- **05 validation** — `A-VAL-01` (5/5 FRs untested), `B-VAL-01` (6/6 FRs untested), `B-VAL-02` (8/8
  FRs untested), `C-VAL-04` (4/4 FRs untested), `D-VAL-01` (1/1 FRs untested), `D-VAL-03` (8/8 FRs
  untested), `D-VAL-04` (4/4 FRs untested), `E-VAL-01` (2/2 FRs untested)
- **06 sandbox** — `B-EXEC-01` (5/9 FRs untested), `C-EXEC-02` (11/13 FRs untested), `C-EXEC-03`
  (12/12 FRs untested), `C-EXEC-06` (4/8 FRs untested), `D-EXEC-02` (8/8 FRs untested), `E-EXEC-01`
  (10/10 FRs untested)
- **07 technical debt** — `TECH-003` (3/3 FRs untested), `TECH-004` (12/12 FRs untested), `TECH-007` (5/5 FRs untested)
- **08 integration** — `INT-US-02` (1/8 FRs untested), `INT-US-03` (4/8 FRs untested), `INT-US-04` (3/3 FRs untested), `INT-US-09` (2/6 FRs untested)

## B — the gate cannot run at all (5 capabilities)

Small, and two different defects wearing one label:

| Capability | |
|---|---|
| `C-EXEC-01` | no requirements of any kind in the design |
| `C-VAL-03` | no requirements of any kind in the design |
| `E-UI-02` | no requirements — but its design is a **record written after delivery** (`TECH-044`, 2026-08-13), so this one is expected |
| `C-SENS-02` | **has `FR-` ids the parser cannot read** — the table format differs |
| `D-SENS-03` | **has `FR-` ids the parser cannot read** — the table format differs |

The last two matter more than the first three. A design with no requirements is visibly empty; a
design whose requirements the checker **silently cannot parse** reports "cannot run" and is
indistinguishable, from the outside, from one that passed. That is the same disease as a
story-scoped check nobody invokes.

- **01 ui glass** — `E-UI-02`
- **02 sensors** — `C-SENS-02`, `D-SENS-03`
- **05 validation** — `C-VAL-03`
- **06 sandbox** — `C-EXEC-01`
- **07 technical debt** — `TECH-008`, `TECH-009`, `TECH-012`, `TECH-014`, `TECH-015`, `TECH-016`,
  `TECH-018`, `TECH-020`, `TECH-021`, `TECH-023`, `TECH-024`, `TECH-026`, `TECH-027`, `TECH-028`,
  `TECH-029`, `TECH-030`, `TECH-032`, `TECH-033`, `TECH-034`, `TECH-035`, `TECH-036`, `TECH-037`,
  `TECH-038`, `TECH-039`, `TECH-040`, `TECH-044`

## C — delivered and clean (8: 2 capabilities + 6 TECH)

- **07 technical debt** — `TECH-001`, `TECH-002`, `TECH-005`, `TECH-006`, `TECH-019`, `TECH-025`
- **08 integration** — `INT-US-21`, `INT-US-24`

## Integration contracts

13 delivered contract entries. Three name no test **file** — a directory, a bare
`pytest -m integration`, or a suite named in prose:

- `INT-US-05-SF03` Intelligent Code Exclusions
- `INT-US-05-SF04` Framework Native Understanding
- `INT-US-21-SUB` Recursive Planning

All three are frozen in `scripts/baselines/proof_tier.json` with a named owner. No delivered
contract cites a file that does not exist, and none is unit-tier only.

## Proposed groupings — for decision, not filed

Deliberately not turned into tickets. Filing 74 tickets would be the inflation the closure contract
now forbids; the point of this list is to decide the shape first.

1. **B is a different problem from A.** A missing FR table is a specification defect; an untested FR
   is a proof defect. They probably want different treatment and should not share a ticket.
2. **A is already itemised per FR by an existing tool.** The work is verification, not
   investigation — which argues for doing it story by story rather than filing it.
3. **`TECH-017` already owns this.** Its stated principle is that the audit must produce findings
   against capability stories, not only contracts. This document is that audit's input; §5 of its
   design carries the summary.
4. **Candidates for their own ticket** are the systemic causes, not the instances — filed
   2026-08-13 as `TECH-047` (nothing runs the gate across delivered work) and `TECH-048` (a design
   the gate cannot parse reports "cannot run", which is indistinguishable from passing).
5. **The correction at the top is the durable lesson.** Category B looked like 31 and is 5. Measure
   the population before measuring the property, or the headline number carries the error.
