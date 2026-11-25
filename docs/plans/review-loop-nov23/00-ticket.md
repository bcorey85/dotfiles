# Review loop defects, batch of 2026-11-23

Source: ~/agent-evals/queue/review-resume-fix-pass-undoes-an-accepted-ask.md
Source: ~/agent-evals/queue/a-fresh-review-run-re-files-a-design-ask-a-session.md
Source: ~/agent-evals/queue/review-loop-round-2-waits-on-reviewer-reports-the.md
Source: ~/agent-evals/queue/review-loop-stop-counts-post-cap-passes-as-rounds.md
Source: ~/agent-evals/queue/phase-asks-refuses-a-session-reject-of-a-user-only.md
Source: ~/agent-evals/queue/code-resume-applies-a-fix-list-with-no-review-loop.md
Source: ~/agent-evals/queue/human-turn-lookup-a-relayed-ruling-takes-a-session.md

`review-loop-re-files-a-design-ask-a-session` was dropped as a duplicate of item 2.

## 1. review-resume-fix-pass-undoes-an-accepted-ask

### Context
Two sightings on 2026-11-23, two lanes. On `fix/comment-put-back-asks` a session accepted an ask (store the question
as its own field and drop the prefix strip). The resume's fix pass added no field, kept the strip, added an old-row
fallback the ruling had excluded, and reverted an earlier accepted rename. The run then hit its cap on findings in
that fallback. On `fix/review-fix-pass-lint` a fresh review run reversed two earlier session rulings (a lazy file
listing, and a file put back to HEAD). Each sighting cost a stopped review and a third failed attempt.

### Done when
A test in tests/scripts fails before and passes after: a resume carries an accepted ask whose ruling text names what
to drop, the fix pass's change keeps the dropped code, and the loop flags the pass as against the ruling and puts it
back instead of moving on.

## 2. a-fresh-review-run-re-files-a-design-ask-a-session

### Context
On 2026-11-23, `fix/comment-put-back-asks`: the session rejected one design ask (judge a reworded comment by
similarity in place of line count) in three runs, and a fourth fresh /review filed it again. Each re-filed ask kept
the run from a clean record, so the push gate stayed shut. The stop's resume line also told a lane session to record
the ruling with `--by user`, though the session ruled it.

(Duplicate item's extra context: the first ruling arrived on a capped packet, and /code reported that the store held
no open asks, so the ruling was never recorded.)

### Done when
A test in tests/scripts fails before and passes after: a branch with a session-rejected design ask from an earlier
review run gets a fresh run whose reviewer raises the same ask, and the loop drops it. A second test: a stop in a lane
session prints a resume line with `--by session`.

(Duplicate item's extra criterion: a session rejects an ask on a capped review packet, a fresh review run on the same
branch raises the same ask, and the loop drops it without a stop.)

## 3. review-loop-round-2-waits-on-reviewer-reports-the

### Context
2026-11-23, agent-evals: a /code run on a plain task ran review round 1 (four real findings, all fixed by the loop's fix coder). Round 2 then failed with a tool fault: the loop asked for reviewer reports under round-2 names, and the fork had dispatched only the round-1 reviewers. Round 2 never ran, so the fix coder's code had no review, and the run handed back a stop. The fix had meanwhile been swept into another session's commit, so unreviewed code reached the branch.

### Done when
A test drives the loop through a round-1 fix pass and shows round 2 either dispatches its reviewers or tells the fork, in its exit line, which reviewers to dispatch under which names; a round-2 wait on reports nobody was told to write fails the test before the fix.

## 4. review-loop-stop-counts-post-cap-passes-as-rounds

### Context
A /code phase ran two full review-and-fix rounds (the cap), then a final read, a class-closure pass, a follow-up fix and a scoped re-review. The packet said review_round 5 and the stop file said "cap-reached (5 rounds)". The lane reported a "5-round cap", and the user asked why the cap was no longer two. The record is wrong: the cap held at two.

### Done when
A test runs a loop that hits the two-round cap and then stops on a post-cap pass. Its packet and stop text name 2 fix rounds plus the post-cap passes by kind (final read, class closure, scoped re-review), and never a round count above the cap. The test fails on the current script.

## 5. phase-asks-refuses-a-session-reject-of-a-user-only

### Context
2026-11-23: a lane's review converged with five asks. One was a fix coder's edit to the toolkit scripts CLAUDE.md, an owner line for a module the same branch later deleted; the loop had already put the file back. phase_asks.py marks any CLAUDE.md edit user_only and refuses a session ruling on it, and the five asks must be ruled in one call, so the lane could not commit. The orchestrating session had to put the question to the user, who said these questions are not theirs to answer.

A reject changes no protected file: the file stays as master has it. Only an accept writes CLAUDE.md, which is what the user-only rule guards.

### Done when
`phase_asks.py rule` accepts a session `rejected` outcome on a user_only ask that edits CLAUDE.md, CLAUDE.local.md or AGENTS.md, and still refuses a session `accepted` on it. A test in tests/scripts pins both.

## 6. code-resume-applies-a-fix-list-with-no-review-loop

### Context
Over two resumes of one /code plan, the fork skipped the phase review loop both times. Its reason was "this was a resume applying your binding fixes". Each resume added about 120 source lines and 110 test lines: new filters, ranking and retry code. Only the coder's own tests checked them. A resume brief with a fix list is new code, not a ruling on old findings.

### Done when
A code-step test resumes a plan with feedback that changes source files. It fails before the fix (the phase closes with no review-loop dispatch) and passes after (the review loop runs on the resume diff unless that diff is empty).

## 7. human-turn-lookup-a-relayed-ruling-takes-a-session

### Context
`decide keep --by user --relayed-by <name>` and `asks-done --relayed-by <name>` look the relaying session up by name in `~/.claude/sessions`. Two live sessions carried the same name, so `session_id_of_name` refused with "2 live sessions are named ..." and nothing was logged. The relaying session's id was known (the cross-session message names its socket, and ListAgents shows its ref), but the flag accepts no id. The only way out is to rename a live session, which needs that session's cooperation.

### Done when
- `--relayed-by` accepts a session id (the `sessionId` of a live row) as well as a name, and the entry and the relayed row record the name of that row.
- A name that several live rows hold still refuses, and the refusal names the id form.
- A test that fails without the change: two live rows share a name, and a relay by the id of one of them is accepted.
