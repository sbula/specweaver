# task.md — B-SENS-03 SF-05, CB-1: the preamble has a name

**Plan**: `docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf05_implementation_plan.md`
**Boundary**: CB-1 of 2 · **FR-15** · **Tier**: unit

- [x] **T1** — Red: `tests/unit/workspace/analyzers/test_chunking_preamble.py`
- [x] **T2** — The run **before the first symbol** carries `symbol="<module>"`
- [x] **T3** — Text between symbols stays unnamed; a class's own header stays unnamed
- [x] **T4** — Two mutants, both directions: the preamble loses its name · every gap gains it
