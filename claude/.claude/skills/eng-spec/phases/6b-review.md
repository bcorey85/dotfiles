# Phase 6.5: Fresh-eyes plan review

19. **Dispatch `plan-reviewer` with paths only**: the
    finalized plan, `00-ticket.md`, and `acceptance-criteria.md` when step 17 wrote one. Never the ledger, research, or a conversation summary — a plan needing those open is one the coder cannot execute.

20. **Loop until a read returns `VERDICT: CLEAN`, max 3 rounds.** Each round is a
    NEW dispatch, never a `SendMessage` continuation. Expect a second read to surface items the first did not.

    `BLOCKER` and `GAP` resolve like a `DESIGN GAP`: with the user, appended to `03-decisions.md`, then back to the owning architect for a revised plan — never hand-patched. `NIT` is yours to fix or drop.

    **`ALT` goes to the user, always.** Put it with the reviewer's three parts intact; never pre-filter. Accepted or declined, it becomes a decision block (declined = considered-and-rejected for `## Approaches Considered and Not Taken`).

    A finding the user rules out of scope is resolved — log it, do not re-raise
    it next round.

    Still `NEEDS CHANGES` after round three: stop, hand over what's outstanding. No fourth round.

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
