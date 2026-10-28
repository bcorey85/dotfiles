---
type: "Change"
title: "code start runs in the checkout the task names and takes its arguments as given"
description: "/code start takes --repo or a Repo: line at the top of the task file and runs in that checkout, so a run handed only a task file no longer lands in the session's cwd and hits another repo's open run. A --task brief passed as one string reaches a planless run, --phase with run notes uses the saved plan, plan --help prints usage, and say.md keeps one Implemented block."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:09:53-05:00"}
seq: 142
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_repo_flag_opens_the_run_in_that_checkout_and_ignores_an_open_run_of_the_cwd_repo"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `start --repo <path>`, or a `Repo:` / `Repo root:` first line in the task file, runs the whole start in that
  checkout. The skill names it.
- A refusal over an open run that another session started offers `status` only, never `--restart`, which would drop
  that session's run.
- A single skill argument that starts with a flag (`--task "<brief>"` as one string) is split with shlex before
  parsing, so `--task` always starts a planless run.
- `start --phase <id> [--restart] <notes>` with no plan path uses the saved plan and passes the notes to the coder.
- `plan --help` and `-h`, after `plan`, `check`, `check --final` or `parse`, print usage and exit 0.
- The review dispatch replaces an earlier `Implemented:` block in say.md instead of appending a second one.

## Evidence

- 2026-10-27: a /code call with only `--task-file` ran start in the session's cwd, found another repo's run and
  stopped, about 37K tokens wasted. The fork then offered `start --restart`, which would have dropped that run.
- A `--task` brief opened the plan's next unticked phase; a `--phase` restart with notes was refused against its own
  usage text; `plan check --help` crashed; a resumed run's say.md held its main block twice.
- Each new test failed before its fix and passes after it.

## Result

- Not fixed: a stop message naming `start --restart` that the script refuses did not reproduce. After a blocker stop,
  `start --restart` dispatches a coder on a plan with open phases.
- Not fixed: asking to `tick` when the next phase's work is already committed. No signal ties a commit to a phase.

## Watch

—

## Back-out

Revert the commit.
