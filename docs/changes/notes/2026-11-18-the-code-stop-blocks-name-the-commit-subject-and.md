---
type: "Change"
change_type: "fixed"
title: "the code stop blocks name the commit subject and write no git command"
description: "/code stop blocks B and C and the phase-boundary sentence give `Commit subject: <subject>` in place of a `! git commit` line, so a fork no longer hands the user a command."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-18T00:17:26-06:00"}
seq: 4
kind: "fix"
components: ["skill/code"]
evidence: ["code-fork-report-hands-user-a-commit-command"]
watches: []
test: "tests/scripts/test_code_skill_text.py::CodeSkillTextTest::test_no_git_command_for_the_user"
asked: ""
proof: []
unmeasured: "Three lines of skills/code/SKILL.md changed what the fork prints. No rule-meter run: no fixture yet runs a /code fork to its stop block. The text test pins the template; whether a fork still adds a commit line on its own is unmeasured and goes to the user."
---

## Change

`skills/code/SKILL.md` line 74, block B Next step 2 and block C's Next line now print `Commit subject: <subject>` and
no `!` line or `git commit` command. `tests/scripts/test_code_skill_text.py` fails on any such command in the skill
or in `agents/code-fork.md`. The two code-skill rows of `docs/rule-anchors.md` carry new hashes.

## Evidence

The stop template printed `! git commit -m "<subject>"`, the main session relayed it word for word, and a subagent's
text handed the user a command, against the global rule. The user asked what made sessions give such lines.

## Result

Two tests in `tests/scripts/test_code_skill_text.py`; `test_guidance_rules.py` updated to the new text.

## Watch

None.

## Back-out

Revert the commit.
