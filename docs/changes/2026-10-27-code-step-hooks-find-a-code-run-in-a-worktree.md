---
type: "Change"
title: "code-step hooks find a /code run in a worktree outside the session's cwd"
description: "The code-step hooks read the run state from the hook event's cwd, which is the session's checkout. A /code run in a worktree never got its launch or hand-back logged, so resume asked for a second dispatch. Every code-step hook now also reads every repo the session pinned."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T09:45:31-05:00"}
seq: 4
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_launch_and_hand_back_from_a_session_whose_cwd_is_another_checkout_reach_the_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `save_state` adds the repo to `~/.claude/state/code-step-sessions/<session id>`, the list of repos whose /code state
  that session pinned.
- The log, hand-back, dispatch and stop hooks read the event's cwd and every repo on the session's list, each state
  folder once. Each repo keeps the old checks: it must hold state, a run, and no pin to another session.
- The dispatch hook skips a repo when the Agent call carries another run's marker, so two /code runs in one session
  never deny each other's launch. The hand-back and stop hooks answer with at most one denial.
- The say hook relays say.md from the same repos as one message, and the plan hook checks an edit of any of their
  plan files.

## Evidence

- Two /code runs on 2026-10-26, one in an agent-evals worktree and one in a dotfiles worktree, each logged only its
  dispatch: no launch, no hand-back. The session's cwd was the agent-evals main checkout, so every hook event loaded
  that checkout's state (stage done) and logged nothing. `resume` then printed "no Agent call for it was launched",
  the fork stopped, and review and verify never ran.
- The new test sends the recorded launch and hand-back events with a cwd outside the repo. Before the fix, `after-coder`
  printed the dispatch again; after it, it waits, then dispatches the review-loop. A second test shows a launch from
  another session in another checkout is not logged. Five more send the stop, early hand-back, thin-prompt, say and
  plan events from the other checkout.

## Result

- All code_step test files pass in the worktree; ruff is clean.

## Watch

—

## Back-out

Revert the commit. Sessions keep the small list files under `~/.claude/state/code-step-sessions/`; nothing reads them.
