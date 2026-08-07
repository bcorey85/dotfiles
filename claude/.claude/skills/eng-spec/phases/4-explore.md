# Phase 4: Architect exploration (explore only — no design yet)

9. **Launch architect agent(s)** by scope (both in parallel for fullstack —
   exploration has no contract dependency). Omit `model`; their frontmatter pins
   it. Give each the ticket and **`02-research.md`**. Read
   `~/.claude/skills/_shared/invariant-survey.md` and insert its "Dispatch text"
   section verbatim as item 2:

   > Explore only — do NOT produce an implementation plan yet. The research
   > document you were given was produced without sight of the ticket; treat it
   > as the factual ground truth and say so plainly where the ticket's premise
   > and the research disagree. Return an **exploration brief**:
   >
   > 1. **Current state** — what exists today, with `file:line` refs
   > 2. <insert the "Dispatch text" section of `~/.claude/skills/_shared/invariant-survey.md` here,
   >    verbatim — it begins "**Invariant survey (do this BEFORE thinking about the
   >    feature)** — inventory the standing invariants…">
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
   > prepended. "There was nothing to decide" is a claim worth checking.

10. If every architect returns a full plan (zero decision points, zero open
    questions), skip Phase 5 and the step-15 finalization; go to Phase 7.
