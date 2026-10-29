---
type: "Change"
change_type: "fixed"
title: "Credential and review-commit blocks tell the agent to carry on"
description: "The review commit gate and the credential-read blocks now tell the agent to continue the task, so a main-session turn no longer ends on the block."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-25T22:18:44-05:00"}
seq: 24
kind: "fix"
components: ["script/review-commit-gate", "script/block-credential-read", "script/bash-safety-gate"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_block_next_steps.py::BlockNextStepTest"
asked: ""
proof: []
unmeasured: ""
---

## Change

The review-commit-gate deny text now says: do not stop or ask the user, invoke the /review skill now, then commit after it converges. The deny text of the shell credential read (cat_creds) and of every credential-file Read block now ends with the approved path: do not read it by another route, carry on without the contents (variable names come from `.env.example`), and name any value the task needs in the final report. The blocks themselves are unchanged. The auto mode classifier is built into Claude Code, is not a toolkit script and carries no text the toolkit can edit, so it stays as it is.

## Evidence

census: in the newest intake, main sessions had 98 turns that ended right after a hook block. By rule: review-commit-gate 29 of 88 blocks, auto mode classifier 22 of 69, cat creds 11 of 42. The old texts named no next step for a credential read, and the commit text only said to run /review.

## Result

Effect unmeasured. A turn that ended on one of these blocks should now continue; the main-turn count in review-queue.txt is the reading. The full suite passes: 2132 tests, 0 failed, lint clean.

## Watch

—

## Back-out

restore the two deny texts and the `NEXT_STEP` lines
