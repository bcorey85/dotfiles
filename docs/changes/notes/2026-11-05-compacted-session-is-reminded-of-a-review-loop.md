---
type: "Change"
change_type: "fixed"
title: "Compacted session is reminded of a review loop waiting on its reviewers"
description: "A new SessionStart hook on resume and compact prints the open dispatch-reviewer lines of every launched review loop of the repo that still runs, so a compaction no longer loses the reviewers and lets the loop time out unseen."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:35:49-06:00"}
seq: 8
kind: "fix"
components: ["script/reviewer-dispatch", "script/waiting-review-launch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_waiting_review_launch.py::WaitingReviewLaunchTest::test_a_running_loop_with_an_unwritten_report_prints_its_dispatch_lines"
asked: ""
proof: []
unmeasured: ""
---

## Change

`reviewer_dispatch.waiting_launch_lines(repo)` lists the dispatch lines of each launch run under `<git path review-script>/loop-script/` whose loop pid runs and whose reports are unwritten. `LAUNCH_STATE_NAME` and `LOOP_FOLDER` move there; `review_launch.py` reads them. New `gates/waiting_review_launch.py` prints those lines as SessionStart additionalContext, skips an `--agent` seat and fails open. It needs a `SessionStart` entry with matcher `resume|compact` in `settings.json`, which the user adds.

## Evidence

judgment: a compaction landed between `launch` and its dispatch notice; the session never dispatched the reviewers, the loop waited 1800 s and stopped with nobody told. Both new tests fail on the base commit (no script) and pass after. Hook median on a compact event in this repo: 28.8 ms, next to 7.6 ms for a bare Python start (20 runs each); it runs only on resume and compact.

## Result

`test_waiting_review_launch.py` 2, `test_reviewer_dispatch.py`, `test_review_fix_script.py`, `test_code_wait.py`, `test_toolkit_self_location.py`: all pass; lint clean.

## Watch

—

## Back-out

Remove the settings entry, `gates/waiting_review_launch.py`, its test and `waiting_launch_lines`/`loop_pid`; restore the literal state names in `review_launch.py`.
