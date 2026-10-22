# The two gates: `quick` and `cb`

## `quick` is not the commit gate

`quick` is the sub-second subset (lint, cognitive complexity, file sizes, conventions and the
test-source guards, diff-scoped) and is meant to be run as often as you like. It is deliberately
NOT the commit gate: `python scripts/quality.py cb` runs at the commit boundary, adds mypy, tach,
the suppression ratchet, class health and cycle detection, and widens every check to the whole
source tree. Never treat a green `quick` as permission to commit.

## The `cb` test scope is narrower than a full sweep

**This is deliberately narrower than a full-suite sweep at every commit boundary.** A capability
story runs unit tests for the packages it touched here, and the full sweep across all tiers
happens at `sf` and `feature`. The trade is bought with the scoping, not skipped: a cross-module
regression surfaces at the sub-feature gate rather than immediately. If a batch touched a
widely-depended-on module and you want the sweep now, `--all` is the honest way to ask for it.
