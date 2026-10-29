---
type: "Change"
change_type: "fixed"
title: "A git grep presence check passes on a hit"
description: "/code verify reads a git grep line the way it reads an rg or grep line: a ban unless its text says it checks presence, so a presence check that finds its match passes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:59:00-05:00"}
seq: 134
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_git_grep_presence_check_passes_plan_check_and_verify_on_a_hit"
asked: "2026-10-27: agent-evals-64 assigned queue item code-step-verify-treats-every-git-grep-line-as-a"
proof: []
unmeasured: ""
---

## Change

- `code_step_boundary.is_search_ban`: a `git grep` line no longer counts as a ban by default. It follows the `rg`/`grep`
  rule: presence wording makes exit 0 pass, ban wording on the same line wins.
- `SEARCH_COMMAND` names `git grep`, and the failure note covers it.
- The presence-wording check for the note reads the line without the command text.
- `plan-format.md` names `git grep` in the ban rule and says a wrapped search is judged by its exit code.

## Evidence

- A plan's Automated Verification item said "the export exists" over a `git grep` command. Verify failed it on the hit.
- Four of the five new tests fail on the old script, among them the presence-on-a-hit test and the
  `test -n "$(git grep ...)"` wrapper test.

## Result

- A `git grep` presence check passes the plan check and verify on a hit and fails on no hit. A `git grep` line with no
  wording stays a ban.

## Watch

—

## Back-out

Revert the commit.
