# Phase 6.5: Fresh-eyes plan review

19. **Dispatch `plan-reviewer` with paths only**: the
    finalized plan, `00-ticket.md`, and `acceptance-criteria.md` when step 17
    wrote one. Never the decision ledger, the research file, or a summary of the
    conversation — a plan that only parses with those open is a plan the coder
    cannot execute, and sending them hides the defect this phase exists to find.

20. **Loop until a read returns `VERDICT: CLEAN`, max 3 rounds.** Each round is a
    NEW dispatch, never a `SendMessage` continuation. Expect a second read to surface items the first did not.

    `BLOCKER` and `GAP` resolve like a `DESIGN GAP`: with the user, appended to
    `03-decisions.md`, then sent back to the owning architect for a revised plan
    rather than hand-patched. `NIT` is yours to fix or drop.

    **`ALT` goes to the user, always, and you never rule on it yourself**. Put it to them with the
    reviewer's three parts intact (what changes, what disappears, what it costs); never pre-filter. Accepted, it is a decision block and a re-finalization
    like any other. Declined, it is a decision block too — the alternative was
    considered and rejected, which is exactly what `## Approaches Considered and
Not Taken` is for.

    A finding the user rules out of scope is resolved — log it, do not re-raise
    it next round.

    Still `NEEDS CHANGES` after the third round: stop, hand the user what is
    outstanding, and let them decide whether to proceed. Do not spend a fourth.

20b. **Log every real BLOCKER and GAP** — one `log-escape` line each,
`stage_found=plan-review gate_missed=eng-spec`, classed as it would have been had
it reached a phase gate. Not a NIT, not a finding ruled out of scope, and **never an
`ALT`**. `ALT`s are counted on the row below.

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
