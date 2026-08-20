# Current task

**None in progress.** The last commit boundary closed cleanly.

This file is the phase tracker `specweaver-pre-commit` writes to while a gate is running. When no
task is in flight it says so, because a finished task left here reads as the live one — which is
what happened for four days with a completed `INT-US-16` sitting in it.

## Where to look instead

| You want | Read |
|---|---|
| What the project is | `.agents/PROJECT.md` |
| How we work | `.agents/PRINCIPLES.md` |
| What is delivered, set back and missing | `.agents/STATE.md` |
| This session's loose ends | `.tmp/HANDOVER.md` (gitignored) |

## Starting a task

Replace this file's contents with the task, then let `specweaver-pre-commit` tick its phases.
Clear it back to this when the boundary closes.
