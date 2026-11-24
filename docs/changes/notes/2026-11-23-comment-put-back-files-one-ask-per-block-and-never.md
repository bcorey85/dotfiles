---
type: "Change"
change_type: "fixed"
title: "Comment put-back files one ask per block and never repeats a ruled ask"
description: "The review loop's comment put-back now files one ask per comment block, does not put back a comment an accepted ask deletes, does not re-ask a comment whose ask was rejected, and files no ask for a comment a fix pass only reworded, so lanes stop hitting the round cap on no-op asks."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-23T04:50:22-06:00"}
seq: 3
kind: "fix"
components: ["script/review-loop"]
evidence: ["lane reports"]
watches: []
test: "tests/scripts/test_review_loop_script.py::CommentRemovalUnitTest::test_an_accepted_block_ask_suppresses_the_put_back_of_every_line_in_it"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `review_loop_comment_removal.py`: lost comment lines group into blocks (consecutive line runs). Each block gets one
  ask that quotes every line.
- A block an accepted ask already covers is not put back. A block whose ask was rejected is put back, and the ask
  is not filed again, even after its line number moved.
- A comment a fix pass reworded in place, into as many comment lines or more, is left alone and files no ask. A
  comment rewritten into code, or a block cut shorter, is still put back.
- An ask covers only the lines the put-back really restored.
- `lib/protected_lines.py`: `rewritten_stretches`, `consecutive_entry_runs` and a shared `line_opcodes`.
- `lib/protected_lines.py` `rewritten_stretch`: a lost line with no alike line in the rewritten stretch now goes
  after the last restored neighbour, not in front of the stretch. The comment put-back and the sign-off put-back
  both use it, so sign-off lines can land in a different place.
- A comment ask's question names the file and the block, never a line, and a rejected ask's row stores that `question` as its own field (`review_asks.record_rejected_asks`,
  `handback_store`). The put-back matches a rejection on that field alone, exactly (`rejected_block`; the
  question names the file). It skips an ask already filed for the same path and question. A rejection recorded before the field existed does not match.
  Wanted asks keep the folded-title match (`rejected_by_title`).

## Evidence

Five sightings in the queue item `review-loop-comment-put-back-re-files-an-ask-a`. Two lanes stopped at the round
cap on per-line asks for reworded comments, 6 asks in one run, and a rejected ask was filed again in the same run.

## Result

The new tests fail on the old put-back code and pass after the change. They cover blocks, rejected asks, accepted asks
and rewording. `bash tests/run.sh` passes.

## Watch

None: the next review runs on the two waiting lanes show whether a no-op put-back ask still comes back.

## Back-out

Revert the commit.
