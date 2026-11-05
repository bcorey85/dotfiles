# Acceptance Criteria — fix-code-run-bugs

> Written before implementation.

- **AC1** — `refactor_flow.py log` refuses an escape finding with no `miss_reason` or a value outside `out-of-scope|needs-other-file|needs-runtime|plan-gap|seen-dismissed|rule-absent|overlooked`, and the escape row it writes carries the finding's `miss_reason`, never `unknown`.
- **AC2** — `refactor_flow.py log` writes a `plan_structure: true` finding with `ruled_by` (`user` or `session`) as `actioned=fixed`, and its finding row carries `ask_decided_by=<ruled_by>`; without `ruled_by` a fixed plan-structure finding is still refused.
- **AC3** — With no review_fix state and a hand-back in the store holding a held plan impact, `review_fix.py decide keep --by session --ruling <text>` exits 0, prints `ACTION: done` and records the ruling, so the commit gate counts the review as clean.
- **AC4** — With no review_fix state and a held plan impact, `decide adopt` writes the deviation entry and prints a stop that sends the caller to rerun its own review loop; with no held impact the "no packet was processed" error stays.
- **AC5** — `stage.mjs --run` prints the `jump-queue` block before the tier report.
- **AC6** — `ledger_deferred.py` runs `ledger worker --once` itself when the ledger is busy and then prints the queue; when it stays busy it exits 75 and says the worker already ran.
- **AC7** — `test_asks_done_from_another_repo_names_the_directory_it_looked_in` compares against the resolved temp path.
- **AC8** — `bash tests/run.sh` passes.
- **AC9** — `refactor_flow.py log --mode simplify` accepts a target whose file the branch deleted (tracked at `HEAD`, gone from the index) and prints it as deleted; a target tracked in neither is still refused.
