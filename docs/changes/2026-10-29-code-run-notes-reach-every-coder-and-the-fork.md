---
type: "Change"
change_type: "fixed"
title: "code run notes reach every coder code_step dispatches for the phase and the fork takes routing notes mid-run as guidance"
description: "The run notes given after a plan now reach every coder code_step dispatches for the phase, not only the first, and a mid-run message that only routes the run or sets a constraint is recorded as guidance instead of being turned away as a scope change."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T21:53:07-05:00"}
seq: 298
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_expected_red.py::ExpectedRedTest::test_run_notes_after_the_plan_reach_the_first_coder_once_and_the_ask_fix_coder"
asked: ""
proof: []
unmeasured: "Mid-run messages the fork turns away are not logged; no intake number reads them."
---

## Change

`start` saves the run notes in the phase's state, and every coder code_step dispatches for the phase carries them
under "Run notes from the user", the same way it carries the main session's guidance. Before, only the first coder saw
them; the ask-fix coder and any later coder of the phase did not. The review-loop agent's own fix coders still do not
get them, and a later phase starts without them. The /code skill now records a mid-run message that routes the run or sets
a constraint on how it works (which tests to run, a session or ref to use) and changes no scope with `guide`, with or
without the `guidance:` start. A message that adds, drops or changes the work the task or the plan names is turned away
as a scope change; any other message, such as a question, gets a reply to ask again after the hand-back.

## Evidence

judgment: a worker started /code with a plan path and a brief holding an orchestrator ref, slot routing and a
scoped-tests rule; later the running fork turned away a routing-only note as a scope change. The new test fails on the
base commit: the ask-fix coder's prompt lacks the run notes. A second test pins the skill rule that sorts routing notes
from scope changes.

## Result

Routing and constraint notes reach every coder code_step dispatches for the phase, whether given at start or mid-run.

## Watch

None.

## Back-out

Revert the commit; run notes reach only the first coder again, and the fork turns away every mid-run message that does
not start with `guidance:` or `asks-done`.
