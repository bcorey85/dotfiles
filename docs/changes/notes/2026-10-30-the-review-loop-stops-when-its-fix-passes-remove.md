---
type: "Change"
change_type: "added"
title: "The review loop stops when its fix passes remove the change under review"
description: "The scripted review loop stops with the new status fix-removed-change when its coder passes have removed half or more of the source lines the change under review adds, so a fix that deletes the mechanism a lane exists to add never converges as clean."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T02:53:02-05:00"}
seq: 313
kind: "fix"
components: ["script/review-loop-script", "script/handback", "script/review-fix", "script/code-step", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_coder_that_removes_the_mechanism_the_change_added_stops_the_loop"
asked: ""
proof: []
unmeasured: ""
---

## Change

- At its start, `review_loop_script.py` records the non-blank source lines the working tree adds to HEAD, in files
  that count toward the size bar. After every coder pass (round fix, class closure, full-check repair) it counts how
  many of those lines no in-scope file still holds, cumulative over the loop. When that is half or more of a change
  that adds 10 or more lines, the loop stops with status `fix-removed-change`. Its blocker line gives the counts and
  the files that lost the most. No full check or class closure runs after it.
- A line moved into another in-scope file, or removed and added back, does not count as removed. Test-file lines
  never count. A rename git reports reads against its old path. A rename git does not report (a plain `mv`) reads
  as a delete plus an add, so the loop stops: a false stop costs less than a gutted fix that ships.
- The new `lib/change_removal.py` does the counting. `handback.py` owns the status word and accepts it as a blocker
  status. `review_fix.py` and the code-step review stops route it as a stop that never marks the gate, and
  code-step's `review-again` accepts it; code-step reads it through `load_handback`, so a missing `handback.py`
  still stops the run. Both review-loop agent files list the seventh status.

## Evidence

A dotfiles hook-fix lane's fix coder, on its third pass, deleted the whole mechanism the lane existed to add. The
tests passed, and the loop would have reported converged.

## Result

Targeted tests pass. A fix pass that deletes the added mechanism stops the loop; a normal fix still converges.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
