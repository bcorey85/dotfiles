---
type: "Change"
title: "Main session sends simple commands after EnterWorktree"
description: "The orchestration rule says Claude Code's own worktree guard refuses chains, $VAR, $(...) and heredocs after EnterWorktree, and to send one simple command per call with literal paths, in the session and in every subagent brief."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:39:43-05:00"}
seq: 77
kind: "fix"
components: ["rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_main_session_is_told_to_send_simple_commands_after_enter_worktree"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `orchestration.md` Git: one bullet after the worktree-location rule. After EnterWorktree, Claude Code's worktree
  guard refuses a Bash command it cannot prove stays off git, even with no git in it. Run one simple command per call
  with literal paths, say so in every subagent brief, and a subagent with no Write works without a scratch script.

## Evidence

- Peer reports on 2026-10-25 and 2026-10-26: chained read-only lookups, a heredoc chained with `rg`, a
  runtime-computed command name, and an `fd` inside `$(...)` were each refused with "cannot be shown not to be git",
  and each passed when split. One Bash-only review subagent traced a regex by hand because it could not run a script.
- No hook in this toolkit emits that text; it is Claude Code's built-in guard, reported upstream (open issue on the
  Claude Code tracker). The research note in agent-evals holds the sources and the comment text for the user to post.
- The test pins the rule text; it fails on the base tree.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
