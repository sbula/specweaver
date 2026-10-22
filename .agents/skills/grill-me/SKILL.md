---
name: grill-me
description: "Interviews the user until a decision is settled, one round of open questions at a
time. Start it yourself when a `PRINCIPLES.md` §2 must-not-guess trigger appears — design Phase 1, a
plan, or any unagreed default — or when the user says 'grill me'."
argument-hint: "[<feature_id> | <topic>]"
---

Every answer in the grilling is the user's. Ask the frontier, then wait. A question
still open stays open — it blocks the phase rather than becoming a default.

1. **Map the decisions as a tree.** Each decision opens the ones that depend on it.
2. **Ask the frontier, in rounds.** The frontier is every open question whose prerequisites are
   already answered. Ask all of it in one round; a question that depends on another question in
   the same round waits for the next round.
3. **Format each question** with at most 2 options and your recommendation, worded so that "yes"
   accepts it:

   ```
   ❓ **Q1 — <title>**: <the context needed to choose; option A; option B>

   ➡️ <recommended answer>
   ```

4. **Find facts yourself.** Never ask the user what you can look up in the repo or the tools;
   send a subagent if it takes long, and ask the rest of the frontier meanwhile. Only the
   decisions go to the user.
5. **Wait for the answers.** End your turn. Each answer settles a node and opens new questions:
   recompute the frontier and ask the next round.
6. **Stop when the frontier is empty** — every branch visited, nothing assumed — and the user
   confirms the shared understanding. Write each settled decision beside the fact it governs,
   marked `[agreed <date>]` (`PRINCIPLES.md` §2). *"You decide"* counts: record it as a delegation
   naming the question and who delegated it.
