# Phase 6.5: Fresh-eyes plan review

19. **Dispatch `plan-reviewer` with paths only**: the saved `spec.md`,
    `00-ticket.md`, and `acceptance-criteria.md` when step 17 wrote one. Never
    the ledger, research, or a conversation summary.

19b. **Shard above 400 lines.** Run
`python3 ~/.claude/scripts/tools/plan_review_shards.py cut <task dir>/spec.md`
and send one parallel dispatch per path it prints, in place of `spec.md`. One
path is the plan itself: one dispatch at the whole file. Two paths are shard A
and shard B in a temp folder outside the task directory; never write a shard
into the task directory. A non-zero exit names a plan defect: fix the plan and
run it again.

    Right after each hand-back, Write it whole to
    `review-round<n>-shard-<x>.md` in the task directory (`a` if unsharded).
    Before round 2 run `python3 ~/.claude/scripts/tools/plan_review_reports.py check <task dir> 2`;
    stop if it fails. Round 2 reads those files.

    When `cut` printed two paths, once both hand-backs are written run
    `python3 ~/.claude/scripts/tools/plan_review_shards.py clean <the folder holding them>`.
    Dedup the two reports by (section, claim) before step 20. A finding only
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

    `BLOCKER` and `GAP` resolve like a `DESIGN GAP`: with the user, appended to `03-decisions.md`, then back to the owning architect for revised section text that you write in (step 16) — never a patch of your own design. `NIT` is yours to fix or drop.

    **`ALT` goes to the user once.** Put it with the reviewer's three parts intact; never pre-filter. Accepted or declined, it becomes a decision block (declined = considered-and-rejected for `## Approaches Considered and Not Taken`). An ALT alone never triggers another round.

    A finding the user rules out of scope is resolved — log it, do not re-raise
    it next round.

    Persist the revised plan in `spec.md` before re-checking or handing off.
    Before re-dispatching, re-check every count, `file:line` citation, and
    cross-reference the repair touched — a stale pointer left by a repair returns
    as the next round's finding.

20b. **Log every real BLOCKER and GAP** — one line each. Not a NIT, not out-of-scope, **never an `ALT`** (counted on the row below). `guard=` is the rung from `~/.claude/skills/_shared/escape-ratchet.md`: `check` when a finalization command would catch it, else `none`.

    ```bash
    ~/.claude/scripts/telemetry/log-escape stage_found=plan-review gate_missed=eng-spec class=<correctness|test-gap|security|perf|other> severity=<high|medium|low> guard=<check|none> desc="<finding gist>"
    ```

21. **Log the plan.** One row, once, now that the plan is final:

    ```bash
    ~/.claude/scripts/telemetry/log-spec-run \
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

Continue to Phase 7 (`7-handoff.md`).
