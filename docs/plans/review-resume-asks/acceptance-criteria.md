# Acceptance criteria

1. A resumed /review that edits files ends with a review round over those edits: the fork cannot write
   `review-stop.md` while asks-done's printed launch line has not run. (Phase 1)
2. A /review resume that names test commands runs them and reports pass/fail counts, or says why it could not.
   (Phase 2)
3. asks-done refuses an `accepted` or `rejected` outcome on an ask with a conditional proposed change and asks for a
   `modified:` answer. (Phase 3)
4. A logged ask outcome can be corrected with `asks-done --correct` before the fix run launches. (Phase 3)
5. A user-accepted ask is applied, or the run stops with the coder's objection as a new ask. It never lands in
   skipped on the coder's or a reviewer's say-so alone. (Phase 4)
6. `asks-done` with no `--by` refuses and logs nothing; a user sign-off is recorded only from `--by user`. (Phase 5)
7. `bash tests/run.sh` passes.
