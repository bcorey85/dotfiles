---
type: "Change"
change_type: "fixed"
title: "Five contradictory skill lines are corrected and the plan-verifier and test-intent-reviewer descriptions name every dispatcher"
description: "Five skill lines each name one action and contradict nothing in their file; the plan-verifier and test-intent-reviewer descriptions name close-branch as a dispatcher; the opencode test-intent-reviewer description names only its own dispatcher."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T16:00:00-06:00"}
seq: 25
kind: "fix"
components: ["skill/orient", "skill/todos", "skill/list", "skill/pull-ticket", "skill/verify-branch", "agent/plan-verifier", "agent/test-intent-reviewer"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_prose_facts.py::ToolkitProseFactsTest::test_verify_branch_does_not_call_itself_the_only_run_site"
asked: ""
proof: []
unmeasured: "Factual corrections to eight lines (orient write line, todos sources line, list file-name line, pull-ticket status line, verify-branch run-site line, two descriptions, the cull scope line); no rule-meter arm carries them."
---

## Change

orient states its only writes (the vault note, the saved walk and the `note` capture line). todos allows exactly the two git commands. list names the full-text file on the line after the list. pull-ticket gives each ticket status one action. verify-branch no longer calls itself the only run site; the sentence was removed with nothing in its place. plan-verifier and test-intent-reviewer descriptions name /close-branch; the cull scope line names it too. The opencode test-intent-reviewer description names /test-audit only, since opencode has no close-branch command.

## Evidence

verify-branch called itself the only run site while close-branch also dispatches plan-verifier; the orient write line contradicted its vault write; todos said both "add git status" and "do not go looking".

## Result

Each line names one action and no line contradicts another in its file.

## Watch

None.

## Back-out

Revert the commit.
