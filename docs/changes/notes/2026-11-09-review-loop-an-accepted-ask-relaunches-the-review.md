---
type: "Change"
change_type: "fixed"
title: "review loop: an accepted ask relaunches the review as a fix run, so its converged hand-back earns commit credit"
description: "When the user accepts or modifies an ask, `review_fix.py asks-done` writes those asks to a findings file and prints `ACTION: redispatch` with a `launch --fix` line that carries the first run's flags. The loop's fix coder applies the asks, a review round covers them, and the converged hand-back earns commit credit. All rejected ends with `ACTION: done`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-09T00:44:09-06:00"}
seq: 1
kind: "fix"
components: ["script/review-fix", "script/review-launch", "skill/review-fork-run"]
evidence: ["judgment", "tests"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_an_accepted_ask_relaunches_the_review_as_a_fix_run_whose_converged_hand_back_earns_commit_credit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_launch.py`: `launch` writes `<loop dir>/handoff.txt`, and its `launch.json` now holds `relaunch_args` beside `packet_args`: the repo, `--base`, each `--file`, `--fast` or `--deep`, the lane and the handoff file. The packet command it prints carries `--launch <loop dir>/launch.json`.
- `review/review_fix.py` `packet --launch` stores those flags in the packet state.
- `review/review_fix_asks.py` (new, the asks-done verb): for each accepted or modified ask that is not a plan impact, it writes `- <file:line> <question> Proposed change: <change>` to `<git dir>/review-fix/ask-findings.md`. A modified ask needs `modified:<the user's change>`, and that change is appended as the one to make. It then prints `ACTION: redispatch` and `review_fix.py launch --fix <file> --iter <rounds used> <first run's flags> --detach`. A packet with no launch record stops with `ACTION: stop-no-launch-record` and names the file. An accepted or modified plan-impact ask goes to no fix run: its change prints as a `## Plan Deviations` entry under the summary, for the session to add to the plan. With no accepted code ask, asks-done prints `ACTION: done`. The old "dispatch a coder" line is gone.
- `review/review_fix_state.py` (new): the state, usage and print helpers moved out of `review_fix.py` so that script stays under 1000 lines.
- `skills/_shared/review-fork-run.md`: on resume, a `redispatch` runs its launch line and waits as for any launch.

## Evidence

Ruling from the orchestrating session agent-evals-09 on 2026-11-09: a resumed `/review` that accepted an ask told the model to dispatch a coder. That coder's edit was never reviewed, so the commit gate refused the tree.

## Result

Against the base script the new test fails: asks-done prints no `redispatch`. With the change, the test walks review → ask → asks-done accepted → the printed launch → converged packet. The findings file holds only the accepted ask, the fix run's prompt carries the first run's files, lane, handoff and `iter: 1`, and `false_clean_reason` is None. New tests for a modified ask, an accepted plan-impact ask, all rejected, a modified ask with no note, and a packet with no launch record pass. Suite: `bash tests/run.sh` passes.

## Watch

None. A run that `launch` did not start prints `stop-no-launch-record` with the findings file.

## Back-out

Revert the commit.
