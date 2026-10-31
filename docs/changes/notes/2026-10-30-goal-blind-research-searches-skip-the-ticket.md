---
type: "Change"
change_type: "changed"
title: "Goal-blind research searches skip the ticket"
description: "goal-blind-researcher hands spec-research one exclude glob naming the task directory and the folder that holds the in-repo source ticket, spec-research drops Grep and Glob and puts the glob on every rg search, and both research children edit files only with Edit or Write, never sed -i."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T11:19:33-05:00"}
seq: 381
kind: "fix"
components: ["agent/goal-blind-researcher", "agent/spec-research", "agent/spec-questions", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_spec_agent_tools.py::GoalBlindTicketExcludeTest::test_spec_research_applies_the_exclude_glob_to_every_search"
asked: ""
proof: []
unmeasured: ""
---

## Change

- eng-spec's research phase passes `goal-blind-researcher` the path of the source ticket file, relative to the
  session working directory, when Phase 1 read the ticket from a file in the repo.
- `goal-blind-researcher` hands `spec-research` one extra line, `exclude: !{<task dir>/**,<ticket folder>/**}`
  (the task directory alone when there is no source file, or the file sits at the top). It names the folder, never
  the file, since a ticket's file name can describe the change. Nothing else about the ticket crosses.
- `spec-research` loses the Grep tool and searches contents only with `rg` in Bash, with the glob as `--glob` on
  every call. It never searches contents with `grep -r`, `find -exec` or `git grep`, and skips any hit inside an
  excluded path unread. A Bash `rg --glob` with a negated brace glob was checked to drop the excluded paths; no live
  check of the Grep tool's `glob` was possible, so the agent no longer relies on it.
- `spec-research` and `spec-questions` change files only with Edit or Write, never `sed -i`, `perl -pi` or a shell
  redirect.

## Evidence

A goal-blind research run grepped the repo, hit the task folder's `00-ticket.md` and the in-repo source ticket, and
so learned the goal it must not see. The same run's children tried `sed -i`, which the shell-write hook blocks.

## Result

The four new tests in `tests/scripts/test_spec_agent_tools.py` fail before the edit and pass after it; the existing Edit-tool test still passes.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
