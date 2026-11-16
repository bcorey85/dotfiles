---
type: "Change"
change_type: "fixed"
title: "An approval ask survives a resume, only the user rules it, and a keep ruling is not asked again"
description: "A coder's edit to CLAUDE.md, CLAUDE.local.md or AGENTS.md stays an open ask across a run that died, a session is refused unless it records a user ruling with --by user, and a resumed run does not file again an ask the session rejected."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-15T16:00:00-06:00"}
seq: 7
kind: "fix"
components: ["script/review-loop", "script/phase-asks", "script/review-fix-asks", "script/review-asks", "script/review-commit-gate"]
evidence: ["review-loop-approval-ask-is-lost-on-resume-and-a"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::ApprovalAskResumeTest::test_a_resumed_run_holds_the_ask_an_earlier_run_filed"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The approval ask is marked `user_only` in the packet's ask entry (`review_loop_packet.ask_entry`, key `ask_outcome_words.USER_ONLY_KEY`). The mark rides the open row in the hand-back store.
- `phase_asks.py rule` and `review_fix.py asks-done` (also `asks-done --correct`) refuse a session ruling on a `user_only` ask unless it is called with `--by user`: exit 2, nothing logged. The refusal (`review_asks.user_only_refusal`) states by itself that only the user rules the ask, never the session, and that the user's outcome is recorded with `--by user`. No skill or prompt text changed. Under `--by user`, `asks-done` logs every outcome row as decided by the user; `rule` logs only the `user_only` asks' rows that way and the other asks of the batch as decided by the session.
- `phase_asks.py list` marks each `user_only` ask and prints the `--by user` line; the open message `code_wait.py review` prints does the same.
- The loop saves the open approval asks in `<git dir>/review-fix/approval-asks.json` (`lib/review_fix_names.py` `APPROVAL_ASKS_NAME`) when it files them, once per coder pass: a JSON object of each path to the blob id of the file's content before the coder pass. A run reloads them at its start (`resume_approval_asks`), files again each path whose content differs from that blob (a coder's own commit of the edit included), and that no ruling finding of the run names, then rewrites the file with the paths it filed again. A run with nothing saved writes nothing. It reads the saved paths and no diff.
- A `rejected` ruling on a user-only ask removes its path from the file at the ruling (`forget_rejected_approval_paths`, called from `phase_asks.py rule`, `asks-done` and `asks-done --correct`). A damaged file stops the ruling with nothing logged.
- The commit gate's unruled-asks deny marks each `user_only` ask `[user only]` and hands it to the user with the `rule --by user` line, so it never prints a line `phase_asks.py rule` refuses.
- On resume only, as a fallback, a path whose ask repeats an ask the session rejected is not filed again (the drop is listed in the packet's dropped asks). A coder's edit in a normal run is always asked about.

## Evidence

Queue item `review-loop-approval-ask-is-lost-on-resume-and-a`: a coder edit to CLAUDE.md followed by a critical-blocker left no ask in the resumed run, and a session could rule the ask without the user.

## Result

New tests in `test_review_loop_ruled.py` (resume, edit gone, rejected, packet flag), `test_phase_asks.py` (`UserOnlyAskTest`, including the refusal text) and `test_review_fix_ask_ruler.py` (the `asks-done` refusal text). Run against the old code, each fails.

Known limit: an approval-only edit the dead run made but never filed (it died before the ask was filed) is not found again. The loop restores asks only from the paths it saved, and a scan of the whole diff for approval-only files was ruled out.

Known exception: `approval-asks.json` is written once per coder pass that files an approval ask, not once per run as `scripts/CLAUDE.md` asks. A single write at the end of the run would lose the ask when the run dies, which is the defect this change fixes.

Rulings (this change ran with no plan folder, so its decision log is here), all by agent-evals-5e (the orchestrating session), 2026-11-15:

- Prompt text the review loop added (`code/SKILL.md`, `_shared/review-fork-run.md`, `docs/rule-anchors.md`) reverted to master: out of scope; skill text needs rule-meter runs. Twice: after phase 1 and after the second review pass. The branch review's ask to add a `[user only]` clause to those two skill lines: left out, the refusal message carries the rule.
- Branch review ask, commit-gate deny prints a `rule` line `phase_asks.py rule` refuses: fix it; script output with a test is in scope.
- Branch review ask, `asks-done --by user` credits every ask of the batch to the user, not only `user_only` asks: keep today's behavior, older than this change; agent-evals-5e queues it separately.
- Branch review ask, `approval-asks.json` written once per coder pass against the once-per-run rule: accepted as an exception (see Result); agent-evals-5e takes the `scripts/CLAUDE.md` wording to the user.
- Size: the fix rounds after the first commit grew the branch past its 24-file limit; the code was cut back to that commit plus the commit-gate fix. The branch-keyed saved file, the damaged-file stop in the loop and the batched hashing went with it. The ask that a read on another checkout deletes the saved asks: accepted only as deleting nothing, moot after the cut (the file has no branch key). The ask to keep a detached HEAD's asks across a commit: rejected, a detached HEAD runs only on benches.
- Review ask at `review_loop_ruled.py:292` accepted: a user `rejected` ruling on a user-only ask drops its path from `approval-asks.json`.
- Review ask at `review_loop_ruled.py:152` (a per-path base for a coder's own commit) rejected: the orchestrator owns git and the loop snapshots before each coder call.
- `approval_asks_store.py` kept as the one owner of the saved approval paths.

## Watch

None.

## Back-out

Revert the commit. A leftover `approval-asks.json` is ignored.
