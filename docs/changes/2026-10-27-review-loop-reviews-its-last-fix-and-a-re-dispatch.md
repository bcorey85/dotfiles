---
type: "Change"
title: "A review-loop hand-back that ends on a fix passes and names the fix files, and a no-reviewer re-dispatch keeps the round count"
description: "The hand-back hook and the review gate accept a clean hand-back whose last step is a coder after a reviewer, review_fix.py packet lists that fix's files in the user text, and a stop-no-reviewer re-dispatch carries iter= and stops on a second miss in a row."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T19:01:09-05:00"}
seq: 128
kind: "fix"
components: ["script/handback", "script/review-fix", "script/code-step", "script/review-loop-script", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_converged_hand_back_ending_on_a_fix_finishes_and_names_the_unreviewed_fix_files"
asked: "2026-10-27: agent-evals-64 ruling on queue items 190, 185 and 214 - keep the 2026-10-25 user rule; fix the check, not the loop"
proof: []
unmeasured: ""
---

## Change

- `handback.py`: the hook needs a reviewer anywhere in the loop, at any round, not one after the last coder. A clean
  hand-back whose last step is a coder after a reviewer is stored with `unreviewed_fix`. `false_clean_reason` refuses only a hand-back
  with no reviewer at all, so `review-gate-mark clean` takes the same case as the packet. The round-2 leniency from
  `2026-10-27-a-review-loop-s-cap-exit-coder-no-longer-marks-its.md` goes: the rule no longer reads the round.
- `review_fix.py packet`: a hand-back with `unreviewed_fix` stays converged or deferred and adds a "Last fix not
  reviewed" section naming the `fixed[]` files. `stop-no-reviewer` prints `iter=<packet iter>` for the re-dispatch, and
  a second hand-back in a row with no reviewer says stop.
- `code_step resume` (`/code`): the hand-back it prints adds the same "Last fix not reviewed" section, through the
  `handback.py` helpers that `review_fix.py` uses.
- `review_loop_script.py`: the driver records `unreviewed_fix` on its clean hand-back row when any coder pass came
  after its last reviewer round: `coder{n}` at the round cap, after an .md-only fix or with every re-review benched,
  `coder-gate`, or `coder-class`. Its review flow is unchanged:
  `2026-10-25-the-review-loop-drops-the-fix-diff-verification.md` stands.

## Evidence

- Queue items 190, 185 and 214: seven of seven `/review` runs over two days ended `stop-no-reviewer` on the loop's
  last fix. Each re-dispatch started at `iter=0`, ran two new rounds and ended on another unreviewed coder.
- New tests fail on the old scripts: a hand-back ending on a coder after a reviewer is denied at round 1, the packet
  names no unreviewed fix files, and the stop prints no `iter=` line.

## Result

- A loop that ends on its fix hands back once, the packet finishes, and the gate marks clean.
- The user text says which files the unreviewed fix touched.

## Watch

—

## Back-out

Revert the commit.
