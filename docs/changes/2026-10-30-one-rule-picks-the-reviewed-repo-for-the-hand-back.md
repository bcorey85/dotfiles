---
type: "Change"
change_type: "fixed"
title: "one rule picks the reviewed repo for the hand-back and the loop transcript"
description: "The dispatch row, the full-suite-in-CI check and the run rows all name the reviewed repo through loop_transcript.reviewed_repo."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T00:49:43-05:00"}
seq: 308
kind: "fix"
components: ["script/handback", "script/review-loop-gate", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::StoreTest::test_the_dispatch_row_and_the_loop_transcript_name_the_same_reviewed_repo"
asked: ""
proof: []
unmeasured: "A review ask, not a session report: no intake row counts a commit credited to one repo while the loop's run rows named another."
---

## Change

`loop_transcript.reviewed_repo(prompt, cwd, scope_root=None, follow_first_path=True)` is the one rule for the repo a review loop reviews. A printed ROOT= line decides alone, and so does a present `repo:` line (read from cwd): each returns that path's work tree top, or None when the path lies outside a work tree. Only when neither is given does the first absolute path the prompt names apply (when a work tree holds it), then cwd. It returns the work tree's real top, or None. `handback.reviewed_repo` and `LoopTranscript.reviewed_root` are gone. The dispatch row (`handback.handle_dispatch` and `/code`'s review script launch), `handback.full_suite_in_ci` and the review-loop gate's run rows all call it. `LoopTranscript.reviewed_repo(cwd, follow_first_path=True)` passes the transcript's prompt and scope root.

The full-suite-in-CI check reads only the ROOT= and `repo:` lines, then cwd (`follow_first_path=False`): a path the prompt names never exempts a repo from the full check. It no longer falls back to cwd when the `repo:` or ROOT directory is missing: it reads as not in CI. A `repo:` line with trailing prose (`repo: ../x and more`) now yields None, so the CI check reads as not in CI.

The prompt `repo:` field match is case-insensitive and accepts leading `-` and `>` prefixes, so `Repo: ../x` and `- repo: ../x` now credit the dispatch row. A `repo:` line wrapped in markdown (`**repo:**`, backticks) now credits the dispatch row too, and a trailing parenthetical such as `repo: ../x (branch b)` is dropped before the path resolves against cwd. The transcript's run rows now name a repo given by the first absolute path, and resolve a relative `repo:` line from the hook cwd, not the process cwd. The first-path match no longer starts inside a URL: `https://host/...` before a real path used to hide the path. A first path that does not exist and goes on after a space as another path segment (`/x/my repo/a.py`) names no repo, so cwd decides: its cut head could lie in another repo. The run rows follow the first path too, the same rule as the dispatch row.

The ROOT= gap stays open: the dispatch row is written before review-scope prints ROOT=, so with no `repo:` line and a ROOT= in another repo than cwd, the commit gate credits the cwd repo while the run rows name the ROOT= repo. A separate queue item re-records the dispatch row from ROOT=.

## Evidence

The commit-credit review raised it as an ask: the dispatch row took the `repo:` line, the first path or cwd, through `work_tree_top`, while the transcript took the scope root or the `repo:` line as given, with no work-tree top and no realpath. The same dispatch could then credit one repo for the commit gate and log run rows or read `Full suite: CI` in another.

## Result

One test feeds the same dispatch to the dispatch hook and to a loop transcript: a `repo:` line, a `repo:` line whose path holds a space, a `repo:` line naming a missing directory, no `repo:` line, a cwd in no work tree, a symlinked `repo:` line and a symlinked first path. Both name the same repo for each of these prompt-only cases; no case prints ROOT=. The test fails against the previous `handback.py`. Other tests cover a URL before the first path, a `repo:` line with a trailing parenthetical, a first path cut at a space, run rows named by the first path, and a CI repo named only by a prompt path, which still owes the full check.

## Watch

None: no intake number reads which repo a run row or dispatch row names. The ROOT= gap above stays open until its queue item ships.

## Back-out

Restore `handback.reviewed_repo` with its `REPO_LINE`, `ABSOLUTE_PATH` and `GIT_TIMEOUT_SECONDS`, and `LoopTranscript.reviewed_root`. Point `handle_dispatch`, `full_suite_in_ci`, `review_loop_gate.log_run_rows` and `code_step_review.launch_review_script` back at them, and revert the test.
