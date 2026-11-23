---
type: "Change"
change_type: "removed"
title: "Folding test-review into test-audit cuts one always-loaded skill description and a routing choice"
description: "The test-review skill folds into test-audit as a review mode, so the always-loaded skill list drops one entry and the two descriptions (98 words) become one (60)."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T23:22:41-06:00"}
seq: 42
kind: "user-rule"
components: ["skill/test-review", "skill/test-audit", "agent/test-reviewer"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-22: deletion and simplification is a priority equal to additions; cut what does not earn its cost"
proof: []
unmeasured: "No intake metric counts calls to one skill, so no edit watch exists; the work skill-usage census is the evidence and a later census of test-audit review calls reads the fold."
---

## Change

Deleted the test-review skill folder. Test-audit gains a `## Review mode` (`/test-audit review [be|fe|fs|branch] [focus]`) holding the scope parsing and dispatch of `test-reviewer`, and its description names the review triggers. The test-reviewer agent description now points at `/test-audit review`. /refactor dispatches the agent directly and needed no edit; no settings.json or script names the skill.

## Evidence

Work skill-usage census (toolkit rows filtered), all time / last 30 days: test-review 7/1, test-audit 22/2. Both dispatch test-reviewer.

## Result

Always-loaded description words go from 98 (test-review 45, test-audit 53) to 60, and one skill entry leaves the list. Callers fixed: 1. Unmeasured beyond the census.

## Watch

None: no intake metric counts one skill's calls.

## Back-out

Restore the test-review folder and the two edited files from git history.
