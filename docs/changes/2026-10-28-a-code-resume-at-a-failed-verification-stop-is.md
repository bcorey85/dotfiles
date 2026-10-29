---
type: "Change"
title: "A code resume at a verification stop is refused before its fork starts"
description: "A PreToolUse hook on Skill denies `/code`, `/code resume` and `/code continue` while the open run is stopped at its Automated Verification (a command failed, or an item could not be run), and names the step the main session runs: fix the cause, then invoke `/code verify`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T21:09:48-05:00"}
seq: 220
kind: "fix"
components: ["script/code-step"]
evidence: ["transcript read"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_a_resume_at_a_failed_verification_stop_is_refused_before_the_fork_starts_and_names_fix_then_verify"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_hooks.py`: new `command_launch_hook`. On a Skill call for `code` whose args are empty, `continue` or
  `resume` (or a resume alias such as `after-plan-edit`, with or without text after it), it reads the state of the
  run the resume acts on (the session's run in the cwd, else the session's only open run); a run at stage `stopped`
  with stop reason `verification` (a failed command or an item that could not be run) denies the call with the step
  to take: dispatch the fix (a coder or /debug, at most 3 attempts), or edit the plan for an item that could not be
  run, then invoke Skill code with `verify`. On the user's word only, `tick <phase>` instead marks the phase done;
  then resume starts the next phase.
- `code_step_core.py`: new `resume_run_repos`, shared by the hook and `enter_run_checkout`, and the resume verb words
  moved here from `code_step_start.py`.
- `code_step.py`: the `launch-hook` verb and its help line.
- `settings.json`: the hook runs as a PreToolUse hook on Skill.

## Evidence

- After a verification stop, `code_step.py resume` returns ask-user with "when the cause is fixed, run verify". The
  /code fork has no Edit tool and the script dispatches no coder, so each resume paid a full fork launch and ended at
  once, and the main session dispatched the fix by hand anyway.
- The test that fails on the base scripts and passes now:
  `test_code_step_resume.py::ResumeTest::test_a_resume_at_a_failed_verification_stop_is_refused_before_the_fork_starts_and_names_fix_then_verify`.
  `test_the_launch_hook_lets_a_resume_through_when_the_run_did_not_stop_on_verification` pins that other stages pass.
  `test_a_resume_at_an_unparsed_verification_item_stop_is_refused_and_names_a_plan_edit` covers the item that could
  not be run.
- The hook checks only the run a resume acts on (the session's run in the cwd, else the session's only open run), so
  a healthy cwd run beside a stopped pinned checkout passes:
  `test_the_launch_hook_checks_only_the_resumed_run_when_a_pinned_checkout_is_stopped_at_verification`.

## Result

- A resume at that stop costs one hook call in place of a fork launch.

## Watch

- None: no intake counts fork launches that end on a verification stop.

## Back-out

- Revert the commit.
