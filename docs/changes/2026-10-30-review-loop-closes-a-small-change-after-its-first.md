---
type: "Change"
change_type: "fixed"
title: "Review loop closes a small change after its first pass"
description: "Past the first round, the review loop gives a coder only blockers, bug, correctness and security findings, and clean-up of the last fix; other findings defer, and a fix that adds a file or a public function becomes an ask."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:24:37-05:00"}
seq: 345
kind: "fix"
components: ["script/review-loop-script", "script/log-review-finding", "agent/review-loop"]
evidence: ["judgment"]
watches: ["review-loop-defers-non-bug-later-round-findings", "review-loop-fixes-first-pass-findings", "review-loop-fixes-first-pass-findings-escapes"]
overlap: "The 2026-10-19 change sends every fix finding of a first-pass review to a coder and owns the two review-loop-fixes-first-pass-findings watches; this edit defers only non-bug findings past the first round, and bug, correctness and security findings keep a coder, so deferred_fixes_per_review_run rises against that watch's good direction, and the watches are read together."
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_second_round_finding_off_the_fixed_lines_defers_with_no_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- Past the first round, `review_loop_script.py` sends a finding to a coder only when it is a blocker, a
  bug, correctness or security finding on any line, or a non-structure finding on a line the previous coder changed
  or that reports a fixed finding again. Every other finding
  goes to `findings_remaining` and logs `source=later-round`. A loop whose only open items are these ends
  `deferred` after a passed full check, else `cap-reached`, which an open class also forces.
- A fix past the first round that needs a new file or a new public function becomes an ask. The coder prompt carries
  the same rule, and the script reads the coder's diff and raises an ask when the coder adds one anyway. A pass holding a blocker is exempt: it may add
  what it needs, and a blocker the coder still leaves unapplied for new code stops at `critical-blocker`. The class-closure and execution-gate repair passes
  carry no such rule.
- `review-loop.md` carries the same limit for the agent path. `log-review-finding` and `finding-log.md` accept
  `later-round` as a reason to defer.

## Evidence

A small change grew under review: later rounds raised new smell findings and fixed them by adding code, which gave the
next round more to read.

## Result

Targeted tests pass. A second-round smell or an off-line non-bug finding gets no coder; a blocker or a bug does.
New code in a second round, in a pass with no blocker, stops at an ask.

## Watch

`review-loop-defers-non-bug-later-round-findings` (non-bug deferred fixes per review run) reads this edit: it rises by
design. `review-loop-fixes-first-pass-findings` (deferred fixes per review run) and
`review-loop-fixes-first-pass-findings-escapes` (review escapes per review run) belong to the 2026-10-19 change. This
edit moves both numbers, so read escapes first, and revert if escapes rise.

## Back-out

Revert the commit.
