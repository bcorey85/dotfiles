---
type: "Change"
change_type: "fixed"
title: "Stop gates skip a question or claim the reply only quotes"
description: "The staged-claim Stop gate no longer reads a permission question the reply quotes in backticks or double quotes as the reply asking, and a stray quote mark hides no real question."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T01:51:19-06:00"}
seq: 6
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_a_quoted_question_is_no_closing_question"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `lib/message_text.py` owns quoted-span dropping for both Stop checks. `permission_question.closing_question` drops a backtick or double-quoted span (straight or curly, one line) whose whole text is one permission question, before the 400-character tail slice. A backticked command inside a real question ("Should I run `git push`?") stays. `staged_claim_gate` calls the same helper with its claim pattern; what it drops is unchanged.

## Evidence

judgment: on 2026-11-07 the Stop gate sent back a main reply whose last sentence cited "`Want me to file the three findings in Jira?`" as an example; the reply asked nothing. The new test fails on the base commit and passes after.

## Result

Median run time over 21 runs: staged_claim_gate 30 ms against a bare Python start of 8 ms. `bash tests/run.sh` 3237 pass.

## Watch

—

## Back-out

Revert the commit's hunks in the named files.
