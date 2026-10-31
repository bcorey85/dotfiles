---
type: "Change"
change_type: "fixed"
title: "Review-loop fix coders load coder-core"
description: "The scripted review loop appends the coder agent's preloaded skills to the fix coder's system prompt, because claude -p --agent does not load the agent's skills frontmatter."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T01:08:44-05:00"}
seq: 312
kind: "fix"
components: ["script/review-loop-script", "skill/coder-core"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_coder_command_carries_the_body_of_the_skills_its_agent_preloads"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `script_utils` gains `frontmatter_skills` and `preloaded_skills_prompt` (with the `FRONTMATTER` and
  `FRONTMATTER_LIST_ITEM` regexes): the skill bodies an agent's `skills:` frontmatter names, each under a
  `Base directory for this skill:` line.
- `review_loop_script.claude_call` appends that text with `--append-system-prompt` whenever it starts an agent.

## Evidence

Read of the call: `claude -p --agent coder` starts the fix coder without coder-core, so it ran without the
terminal-implementer and hook-block rules.

## Result

A fix coder's command now carries the coder-core body. The new test fails without the `claude_call` edit (no
`--append-system-prompt` in the command). Targeted tests and ruff pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. Where another branch also adds `frontmatter_skills` and `preloaded_skills_prompt`,
whichever branch merges second drops its copy and keeps the first one's version.
