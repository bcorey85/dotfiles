---
type: "Change"
title: "The Django gate test command runs with --noinput"
description: "A derived `manage.py test` gate command asked before deleting a leftover test database, hit EOF and ran no tests, so the coder used up its gate denials on a green change; it now carries --noinput unless the listed command already has --noinput or --no-input."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:54:45-05:00"}
seq: 205
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_django_phase_that_names_an_app_tests_module_runs_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_gates.python_test_command` appends `--noinput` to the `manage.py test` command it derives, after the
  listed options, unless they already hold `--noinput` or `--no-input`.
- A test command the phase lists for a scope smaller than the suite is still taken verbatim.
- Not done: keeping the gate from running while the review loop's full suite runs in the same worktree. That needs a
  cross-process lock, and the report's failure was the prompt.

## Evidence

- A queued report: the gate's Django test command stopped at the delete-test-database prompt, ran no tests, and the
  run flagged a gate cap the code did not earn.

## Result

- The Django gate tests now read `--noinput` on every derived command, and a listed `--no-input` is not doubled. They
  failed before.

## Watch

—

## Back-out

Revert the commit.
