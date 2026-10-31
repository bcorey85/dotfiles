---
type: "Change"
change_type: "fixed"
title: "A stale code-step state file no longer hides a run in another repo"
description: "A /code run in a sibling worktree now logs its launch and takes its coder's hand-back when the session cwd holds a state file this code cannot load. The hooks skip that repo with its error on stderr and reach the session's other repos."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T10:14:42-05:00"}
seq: 369
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_launch_is_logged_when_the_session_cwd_holds_a_state_file_this_code_cannot_load"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `hook_repo_states` catches `StateFileError` per repo, prints the error on stderr and goes on to the session's next repo.

## Evidence

- One run with `--repo` on a sibling worktree never logged its launch, so every `resume` asked for a second dispatch. The session cwd held a state file with keys this code did not know. A second session reproduced it with `log-hook`.

## Result

- The new test fails without the catch and passes with it. `test_code_step.py` passes: 612 tests, 0 failed.

## Watch

None: this fires on a rare stop, and no intake number counts it.

## Back-out

Revert the commit.
