---
type: "Change"
title: "code_step's gone-review-script stop names the pid, the agent and the end of the script log"
description: "When the pid probe reads the review script as gone, the stop text names the pid, the agent whose hand-back is missing and the last lines of the script log."
generated: {"by": "claude-code/sonnet-5-5", "at": "2026-10-28T19:07:20-05:00"}
seq: 199
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_review_script.py::GoneReviewScriptTest::test_the_stop_names_the_pid_the_agent_and_the_tail_of_the_script_log"
asked: ""
proof: []
unmeasured: ""
---

## Change

`stop_on_gone_review_script` in `code_step_core.py` now names, in its stop text, the pid that is not running, the agent
whose hand-back is missing ("(none logged)" when no launch is logged) and the last lines of the script's log. The log
tail comes from the shared `script_utils.file_tail`.

## Evidence

A converged review loop was stopped as invalid-packet on resume. The packet parser and the whole resume path accept
the same packet, so the stop came from the gone-script branch. Judgment: the cause of the missed hand-back is not
yet known; the longer stop text lets the next sighting be diagnosed.

## Result

Fail-first: the stop-text test failed on the unchanged source (the stop named no pid, agent or log tail) and passes
now. The suite for the review script passes.

## Watch

—

## Back-out

Revert the commit; the stop returns to its short text.
