---
type: "Change"
change_type: "fixed"
title: "A /code run's dispatches name its checkout, and later verbs follow the run from any cwd"
description: "Every agent code_step.py dispatches is told the run's checkout as an absolute path and to work only there, and every verb after start goes on with the session's open run when the shell stands in another repo."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T16:46:46-05:00"}
seq: 113
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_checkout.py::CheckoutTest::test_a_run_started_in_a_repo_that_is_not_the_cwd_dispatches_its_coder_again_there_from_the_cwd"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `emit_dispatch` puts one line before every dispatch prompt (coder, plan-coder, asks-coder, review-loop): the run's
  checkout as an absolute path, and to read, edit and run commands only there. The code skill tells the agent to name the
  checkout in every agent prompt it dispatches.
- Every verb after `start`, and `status`, first looks for the session's open run. When the cwd's repo holds none and
  one other pinned repo does, the verb runs there. When several do, it stops and names each checkout.
- The code skill says to run `start` from the root of the repo the task names; later verbs find the checkout
  themselves.

## Evidence

- A /code call named a dotfiles worktree while the session's cwd was agent-evals. The coder prompt named no checkout,
  so the coder worked from the inherited cwd and edited the dotfiles main checkout, the live config of every session.
- The new tests start a run in one repo and run `resume` and `status` from another. Six of the seven fail on the old
  scripts: the prompt names no checkout and the other repo shows no run.

## Result

- A coder dispatched from a run started in another checkout is told which checkout to edit, and the fork's later verbs
  reach that run from the session's cwd.

## Watch

—

## Back-out

Revert the commit.
