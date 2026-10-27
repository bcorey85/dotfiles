---
type: "Change"
title: "spec-criteria numbers ids flat and runs plan check before it returns"
description: "spec-criteria gets Bash for one command: it runs plan check on the spec and fixes its criteria file until every remaining row starts with the spec's path, with flat unique ids and no reason text on a verbatim ticket AC line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:47:31-05:00"}
seq: 83
kind: "fix"
components: ["agent/spec-criteria"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_spec_criteria_numbers_ids_flat_and_runs_plan_check_before_it_returns"
asked: ""
proof: []
unmeasured: ""
---

## Change

- spec-criteria's tools gain Bash, used for plan check only.
- Ids are flat `AC1` to `ACn`, unique across every section, never lettered. A verbatim ticket AC line holds the
  ticket's words; a manual-only reason goes on the next indented line.
- Before it returns, it runs `code_step.py plan check` on the spec and fixes its file until every remaining row starts with the spec's path, then
  returns those rows unedited (it may return on exit 1).

## Evidence

- Two eng-spec runs handed back criteria files that plan check rejected: lettered sub-ids that collided with their
  parent, an id used twice across sections, and reason text appended to verbatim ticket ACs that failed the drift
  check. Each time the main session fixed the file by hand.
- The test pins the tool and the rules; it fails on the base tree.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
