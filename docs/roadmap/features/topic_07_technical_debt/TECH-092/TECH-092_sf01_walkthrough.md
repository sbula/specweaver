# Walkthrough: TECH-092 SF-01 — Settle each tool round

Plan: [TECH-092_sf01_implementation_plan.md](TECH-092_sf01_implementation_plan.md).

## CB-1 — the collector settles each round (FR-1..FR-4)

### What changed

- `TokenUsage.__sub__` (`infrastructure/llm/models.py`): what a running sum added since an earlier
  value of it; subtracting nothing leaves the sum; an unknown cached count stays unknown.
- `TelemetryCollector.generate_with_tools`: the round hook takes the usage summed so far
  (`used_so_far`, optional until the adapters pass it in CB-2). For round ≥ 1 it first settles the
  rounds finished since the last settlement (`_Rounds.settle`: their real cost counts, their
  reservations are released), then reserves the next round. A round that reported no usage counts
  its worst case (`_cost_of`).
- The finished loop's `_capture` and the failed loop's `_record_failure` add only the usage the
  settled rounds did not count; the ledger row still carries the loop's total.

### Red first

`test_token_usage_sub.py` (no subtraction); `test_collector_circuit_breaker.py`: the loop double
passes `used_so_far` (TypeError: the hook took two arguments), five cheap rounds now finish where
round 4 was refused, a round with no usage counts its worst case.

### Tests changed

- `test_every_tool_round_is_checked_before_its_request` expected five cheap rounds to stop after
  three: it counted reservations, the defect itself. It became
  `test_a_round_is_refused_when_what_was_spent_and_its_worst_case_cross` (rounds of USD 2.00 real
  cost; the fifth would cross USD 10).
- `test_the_round_check_sees_the_prompt_grow`: round 1's worst case now crosses the limit on its own
  (round 0 is settled at its real USD 0.20, no longer held at USD 2.25).
- Mutants: the TECH-092 corpus (FR-1 `finished-rounds-stay-reserved`, FR-2
  `unreported-round-is-free`, FR-3 `later-rounds-unchecked`, FR-4 `settled-rounds-counted-again`,
  `failure-counts-settled-rounds-again`), all killed. B-FLOW-05 `failed-tool-call-not-counted`,
  `failure-usage-ignored`, `no-usage-is-free` re-pointed at today's lines and killed; eight more
  collector mutants (B-FLOW-05, C-FLOW-01, C-FLOW-14, E-INTL-01, TECH-074) re-run and re-pinned.
