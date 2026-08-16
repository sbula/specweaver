# US-16: AI Operations & Cost Routing - Integration Contracts

## Base Story Contract (`INT-US-16`)
* **Status:** 🟡 In progress — [design APPROVED 2026-08-16](../../features/topic_08_integration/INT-US-16/INT-US-16_design.md);
  CB-1 (collector wiring, seam pinned) committed; CB-2 (the journey e2e + two fixes) open.
* **Integration Description:** The Implementation Generator (`D-INTL-01`) must run under an adapter
  the Telemetry DB (`C-FLOW-01`) can account for, so that a real `sw implement` run — routed to its
  model by Static Routing (`D-FLOW-03`) — persists one `llm_usage_log` row per LLM call and
  `sw usage` then shows that run's tokens and cost for the active project. The seam has three links
  and each is owned here: `create_llm_adapter` wraps the adapter in a `TelemetryCollector` when a
  project is given; the command places that collector on `RunContext.model.llm`; and
  `PipelineRunner._flush_telemetry` drains it in a `finally`, so a run that **fails** still records
  what it spent. Cost is priced from `sw costs set` where the user has set a rate.
* **Verifiable Proof (CB-1):**
  `tests/integration/workflows/implementation/test_implement_collector_wiring.py` — the collector
  arrives on the `RunContext` the command itself builds (captured, never constructed); a real run's
  rows carry the model that answered; a **failed** run still records its spend; no active project
  stops the command before any adapter is built; and a project name carrying SQL metacharacters is
  refused at registration rather than reaching the telemetry key.
  CB-2 adds the `sw implement` → `sw usage` journey e2e.

> **Why this contract was written after its capabilities shipped.** All four US-16 MVS entries were
> `✅` while this file said `⬜ Pending` with `[Pending definition...]`, exactly the shape recorded
> under `INT-US-25`. Measured 2026-08-16: the machinery was **complete and correctly wired** — the
> opposite of what that precedent predicted — but nothing joined it. The write half was proven from
> the factory down to DB rows, the read half from a **hand-seeded `sqlite3` INSERT** up to
> `sw usage`, and no test crossed the middle. A seam that meets at a fixture rather than at a run.
>
> Two beliefs recorded here as fact did not survive being run, and both were about the same command:
> `sw implement` with no active project does **not** silently spend untracked money — it refuses,
> with a message about a database lookup that failed on the string `None`. And `sw costs set`
> reaches **no** run at all: no command passes `cost_overrides` into `create_llm_adapter`, so a
> configured price is echoed back by `sw costs` and then ignored. Both were derived by reading the
> code and both were wrong in the direction of alarm. See `AD-5` in the design.

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet. The four add-on groups in the roadmap
  (Dynamic Data-Driven Routing, Friction Analytics Dashboard, Enterprise Thought Observability,
  Remote UI Integration) are all blocked on unbuilt capabilities and, per `ADR-003`, each will own
  its own integration and e2e proof as FRs of the capability that creates the seam.

> **Registry note.** `master_story_roadmap.md` lists `✅ Step 9a: Token Tracking` among this story's
> MVS. It is a legacy prose label with no capability ID (`docs/ORIGINS.md:64`), so no gate can
> resolve or verify it — the one US-16 MVS entry that is unfalsifiable as written.
