---
type: "Change"
title: "The /code fork runs as an agent with no Edit or Write tool"
description: "The /code skill forks into a new code-fork agent that has no Edit, Write or NotebookEdit tool, so the fork can no longer implement a brief itself and skip the coder gate and review loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T13:24:10-05:00"}
seq: 55
kind: "fix"
components: ["skill/code", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeForkToolsTest::test_the_code_fork_agent_has_no_tool_that_edits_a_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New agent `code-fork` (sonnet) with `disallowedTools: Edit, Write, NotebookEdit`. The /code skill's `agent:` line
  names it in place of `general-purpose`.
- `FORK_AGENT_TYPE` in the code-step scripts is now `code-fork`, so the hand-back and stop hooks match the /code fork
  only, not every general-purpose agent in the pinned session.
- Bash writes stay possible; the shell-write-gate still refuses redirection onto tracked files and in-place edits.

## Evidence

- A /code call with a step-list brief: the sonnet fork edited the files and ran the tests itself, never ran
  `code_step.py start`, so no coder gate, phase check or review ran. The skill listed `allowed-tools` without Edit or
  Write, but the skills docs say `allowed-tools` only pre-approves tools and never removes one.
- Headless probe on Claude Code 2.1.310: a forked skill on `general-purpose` listed Edit and Write; the same skill on
  an agent with `disallowedTools: Edit, Write, NotebookEdit` listed neither. Hook events from that fork carry the
  custom agent name as `agent_type`.
- The new tool test fails on the base tree and passes after.

## Result

- Full dotfiles suite and ruff check pass on the worktree.

## Watch

—

## Back-out

Revert the commit.
