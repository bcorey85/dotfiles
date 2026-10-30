---
type: "Change"
change_type: "changed"
title: "Review clean status has one owner"
description: "handback.record_clean_review is the one judge and the one writer of review commit credit: review-gate-mark clean, the review-loop packet and the /code phase boundary all call it, it records the tree of the repo the stored dispatch reviewed, and the separate clean file and the session-wide clean line are gone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T23:39:58-05:00"}
seq: 305
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_clean_status_one_owner.py::CleanStatusOneOwnerTest::test_every_site_gives_the_one_answer_of_the_owner_for_the_same_rows"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `handback.record_clean_review(session, committing_session=None)`: runs `false_clean_reason`, and on a clean
  review records the tree of the repo in the latest stored review dispatch through `reviewed_tree.record_reviewed`.
  It returns the refusal or None, and the repo.
- `review_commit_gate.apply_mark`, `review_loop_packet.write_handback_rows` and
  `code_step_boundary.mark_review_gate_clean` call it in place of their own judgement and write. The packet and the
  /code boundary now credit the dispatch repo, not their own repo argument.
- Deleted: the `clean` file the /code boundary wrote per committing session, and the `clean` line `apply_mark` wrote
  to the session state file. Commit credit rests on the reviewed-tree record or a current hand-back of that repo. A
  leftover `clean` line reads as an unreadable line.
- A cap-exit hand-back that ends on an unreviewed coder fix still earns credit; its tests are unchanged.

## Evidence

Read of the three writers at integrate/restart-bugs 595728a5: each judged clean and wrote credit its own way.

## Result

Every former site gives the owner's answer for the same hand-back rows; a test pins it. Targeted tests pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
