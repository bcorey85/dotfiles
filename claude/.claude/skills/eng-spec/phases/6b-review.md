# Phase 6.5: Fresh-eyes plan review

19. **Dispatch `plan-reviewer` with paths only**: the
    finalized plan, `00-ticket.md`, and `acceptance-criteria.md` when step 17 wrote one. Never the ledger, research, or a conversation summary — a plan needing those open is one the coder cannot execute.

19b. **Shard above 400 lines.** `wc -l` the plan. At or under, one dispatch at
the whole file. Over, three parallel dispatches, each a `sed`-derived extract
written to the task directory — the plan itself is never split:

    - **A** — front matter + phases up to the boundary nearest the midpoint + back matter
    - **B** — front matter + the remaining phases + back matter
    - **seam** — front matter + back matter + every `**File**:` line and
      `#### Automated|Manual Verification` heading grouped under its phase
      heading, **no phase bodies**

    Front matter is everything above `## Implementation Steps`; back matter is
    everything from `## Constraints` down.

    Tell the seam reviewer its view is lossy: a phase's prose is absent, so a
    contradiction it reads between two phases' `**File**:` lines is **provisional**
    — report it as a GAP naming the two phases, never a BLOCKER. Only a claim it
    verified against the repo or against front/back matter may be a BLOCKER.

    Dedup the three reports by (section, claim) before step 20. A finding only
    one shard raised still counts.

20. **Review rounds: STANDARD max 1, DEEP max 2.** Round 1 is a NEW dispatch,
never a `SendMessage` continuation. A DEEP round 2 is a NEW dispatch carrying
the prior findings plus the repair diff — a verification pass scoped to the
diff and what it touches, not a fresh read.

    Only BLOCKER and GAP re-dispatch. An ALT never triggers another round.
    `VERDICT: CLEAN` (no BLOCKER or GAP — a lone ALT still reads CLEAN) ends the
    loop. After the last round, outstanding BLOCKER/GAP go to the user as-is. No
    third round.

    **Report the delta after round 1**: findings, and how many the previous
    repair created.

    `BLOCKER` and `GAP` resolve like a `DESIGN GAP`: with the user, appended to `03-decisions.md`, then back to the owning architect for a revised plan — never hand-patched. `NIT` is yours to fix or drop.

    **`ALT` goes to the user once.** Put it with the reviewer's three parts intact; never pre-filter. Accepted or declined, it becomes a decision block (declined = considered-and-rejected for `## Approaches Considered and Not Taken`). An ALT alone never triggers another round.

    A finding the user rules out of scope is resolved — log it, do not re-raise
    it next round.

    Before re-dispatching, re-check every count, `file:line` citation, and
    cross-reference the repair touched — a stale pointer left by a repair returns
    as the next round's finding.

20b. **Log every real BLOCKER and GAP** — one `log-escape` line each (`stage_found=plan-review gate_missed=eng-spec`). Not a NIT, not out-of-scope, **never an `ALT`** (counted on the row below).

21. **Log the plan.** One row, once, now that the plan is final:

    ```bash
    bash ~/.claude/scripts/log-spec-run \
      repo="$(basename "$(git rev-parse --show-toplevel)")" \
      slug=<task dir basename> ticket=<ID|none> verdict=finalized \
      phases=<count> criteria=<count> decisions=<count> \
      research_q=<count> gaps=<count> falsified=<count> \
      plan_review_findings=<count> plan_review_rounds=<count> \
      plan_review_alts=<raised> plan_review_alts_taken=<accepted>
    ```

    Count them, do not estimate: `criteria` is every `Success Criteria` bullet
    across all phases plus every id in `acceptance-criteria.md`; `gaps` is the
    DESIGN GAP items Phase 6 raised and resolved; `falsified` is how many factual
    claims its sweep found wrong and repaired; `plan_review_findings` is BLOCKER
    plus GAP across every round of step 20; `plan_review_alts` and
    `..._taken` are alternatives raised and accepted. Zero is a real answer for every one of
    them and must be logged as such.

    Log `verdict=abandoned` instead if the plan is dropped after research.

    Non-blocking: if the script fails, say so in one line and continue.
