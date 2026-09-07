# Phase 4: Architect exploration (explore only — no design yet)

9. **Launch architect agent(s)** by scope (both in parallel for fullstack —
   exploration has no contract dependency). Give each the ticket and **`02-research.md`**:

   > Explore only — do NOT produce an implementation plan yet. The research
   > document you were given was produced without sight of the ticket; treat it
   > as the factual ground truth and say so plainly where the ticket's premise
   > and the research disagree. Return an **exploration brief**:
   >
   > 1. **Current state** — what exists today, with `file:line` refs
   > 2. **Invariant survey (do this BEFORE thinking about the feature)** —
   >    inventory the standing invariants of every surface the change will touch,
   >    stated independently of what the feature wants: identity/uniqueness
   >    construction, persistence formats and replay paths, ordering guarantees,
   >    authority/permission enforcement points (including paths that BYPASS the
   >    usual boundary — schedulers, hooks, headless execution), mode flags that
   >    change how tokens/data are classified, and lifecycle/liveness
   >    discriminators (for every entity the change will reclaim, expire, evict,
   >    revoke, or invalidate: what does "gone" mean for it, per the system that
   >    owns it?). Categories are examples, not the checklist — also apply the generative rule:
   >    for each entity a destructive action targets, enumerate its FULL state machine
   >    and what the trigger does in each state. When evaluating a candidate trigger signal,
   >    check it BOTH ways — states where it fails to fire (leak) and states where
   >    it fires but shouldn't (false destruction) — and say which cost is worse.
   >    For liveness, "gone" = the owning system's own registry/listing — still listed or resumable = ALIVE.
   >    EVERY teardown path (fast-path included) must satisfy the same gone-condition, never a cheaper proxy. Emit
   >    one line per category — explicit "none found: <checked>" is valid; silently skipped is not. Each with `file:line`.
   > 3. **Patterns** — to follow and to avoid, with refs
   > 4. **Constraints** — technical and convention constraints you found
   > 5. **Counter-priming** — three implementation approaches you considered and
   >    are NOT recommending, one line each on why not. Cannot name three → say so
   >    explicitly; that is diagnostic, not a step to skip.
   > 6. **Decision points** — every place two or more viable approaches exist,
   >    each with options, pros/cons, and your recommendation.
   > 7. **Open questions** — ambiguities only the user can resolve.
   >
   > Exception: genuinely NO design decisions (exactly one reasonable approach) →
   > say so and return the full plan instead, with item 5 still REQUIRED,
   > prepended.

10. If every architect returns a full plan (zero decision points, zero open
    questions), skip Phase 5 and the step-15 finalization; go to Phase 7.
