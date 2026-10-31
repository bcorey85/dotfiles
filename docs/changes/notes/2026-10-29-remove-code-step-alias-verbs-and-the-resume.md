---
type: "Change"
change_type: "removed"
title: "Remove code_step alias verbs and the resume argparse"
description: "code_step.py no longer accepts the verbs after-coder, after-review and after-plan-edit: each is refused as an unknown verb, and every route runs the stale-phase check except a real hand-back of the run's own agent. A resume answer that starts with a dash is still refused, by a plain check in place of an argument parser."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T11:27:45-05:00"}
seq: 259
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_former_resume_alias_is_refused_as_an_unknown_verb_and_changes_nothing"
asked: ""
proof: []
unmeasured: "The skill calls only resume, so no intake number reads the removed verbs."
---

## Change

- `code_step.py` drops the verbs `after-coder`, `after-review` and `after-plan-edit` and the continuation flag that made them skip the stale-phase check. `resume_route` and `command_resume` take no flag; every route runs the stale-phase check, and a real hand-back of the run's own coder or review loop still skips it. The route names `after-coder` and `after-review` that `resume_route` returns stay: they are routes, not verbs.
- The task words the code skill runs as `resume` stay `continue`, `resume`, `after-coder`, `after-review` and `after-plan-edit`: a user who types an old word after `start` or `/code` is refused and pointed to `resume`, and the launch hook treats it as a resume call. As CLI verbs the three are refused as unknown.
- `timed_command` and `next_after` take no verb argument; they always name the resume verb.
- `code_step_usage.py` replaces the argument parser of `resume` with a check on the first word: an answer that starts with `-` exits 2 with the same message and usage. A dashed later word is still accepted.
- The unlaunched-dispatch notice and the relaunch denial always name `resume`; `record_dispatch` and `emit_dispatch` take no verb and the dispatch event no longer logs one.

## Evidence

- The skill and every printed command call `resume`; a search of the toolkit found no caller of the removed verbs.
- The new test fails before the change: each alias exited 0 and did what `resume` does.

## Result

- The alias test passes. The resume, hand-back, cap-reached, review-script, termination, start-input, fixes and asks tests pass with their calls changed to `resume`, and ruff is clean on the changed files.

## Watch

—

## Back-out

Revert the commit. The three alias verbs then resume the run again without the stale-phase check.
