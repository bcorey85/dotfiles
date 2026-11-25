# Acceptance Criteria — review-loop-nov23

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

Ticket ACs are copied verbatim (AC1-AC11). AC12 onward are behaviors observable from the ticket's contexts.

- **AC1** — A test in tests/scripts fails before and passes after: a resume carries an accepted ask whose ruling text names what to drop, the fix pass's change keeps the dropped code, and the loop flags the pass as against the ruling and puts it back instead of moving on.
- **AC2** — A test in tests/scripts fails before and passes after: a branch with a session-rejected design ask from an earlier review run gets a fresh run whose reviewer raises the same ask, and the loop drops it.
- **AC3** — A second test: a stop in a lane session prints a resume line with `--by session`.
- **AC4** — (Duplicate item's extra criterion:) a session rejects an ask on a capped review packet, a fresh review run on the same branch raises the same ask, and the loop drops it without a stop.
- **AC5** — A test drives the loop through a round-1 fix pass and shows round 2 either dispatches its reviewers or tells the fork, in its exit line, which reviewers to dispatch under which names; a round-2 wait on reports nobody was told to write fails the test before the fix.
- **AC6** — A test runs a loop that hits the two-round cap and then stops on a post-cap pass. Its packet and stop text name 2 fix rounds plus the post-cap passes by kind (final read, class closure, scoped re-review), and never a round count above the cap. The test fails on the current script.
- **AC7** — `phase_asks.py rule` accepts a session `rejected` outcome on a user_only ask that edits CLAUDE.md, CLAUDE.local.md or AGENTS.md, and still refuses a session `accepted` on it. A test in tests/scripts pins both.
  - Narrowed by a recorded sign-off (03-decisions.md D5, agent-evals-c3-owner, 2026-11-23): see AC13.
- **AC8** — A code-step test resumes a plan with feedback that changes source files. It fails before the fix (the phase closes with no review-loop dispatch) and passes after (the review loop runs on the resume diff unless that diff is empty).
- **AC9** — `--relayed-by` accepts a session id (the `sessionId` of a live row) as well as a name, and the entry and the relayed row record the name of that row.
- **AC10** — A name that several live rows hold still refuses, and the refusal names the id form.
- **AC11** — A test that fails without the change: two live rows share a name, and a relay by the id of one of them is accepted.
- **AC12** — After a fix pass is put back for going against a ruling, the stopped review leaves the files byte-for-byte as they were before that pass and names the ruling and the file in the stop.
- **AC13** — A session rejecting an ask for a wanted change to CLAUDE.md, CLAUDE.local.md or AGENTS.md is logged as a session ruling; a session accepting it, a session rejecting an ask to keep a coder's edit to those files, and a session ruling on a criteria ask stay refused and log nothing.
- **AC14** — When a capped review's session has ruled its asks, the run is not reported clean by that ruling alone, and an accepted ask on it is recorded for the resume to apply rather than applied before the stop.
- **AC15** — A review that converges in round 1 and then runs a class-closure pass reports 1 fix round and prints no cap line.
- **AC16** — A /code resume whose feedback changes no source (empty diff, or notes only) writes its stop without a review being demanded.
- **AC17** — A /code resume that changed source and tries to write its stop with no review loop run is refused once, with the changed files named and the review start step named; once a review loop has run, the stop is written.
- **AC18** — A relay by a session id that no live session holds refuses, and a relay by a name that one live row holds keeps working.
- **AC19** — Packets written before this change (no fix-round, post-cap or against-ruling fields) still read, and print no cap summary line.

## Manual only

- **AC20** — Running the smoke-test checklist from the closing recap by hand against a real lane (a lane session's stop line says `--by session`; a real /code resume with a source edit is stopped from writing its stop). No automated test can cover a live session's id and live hooks together.
