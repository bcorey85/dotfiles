---
type: "Change"
change_type: "changed"
title: "Sign-offs go only in the decision log"
description: "The global AC rule now names where a sign-off is recorded: the plan's decision log, never code, comments, fixtures or commit messages. coder-core bans the user's name and sign-offs from every file a coder writes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T16:00:00-05:00"}
seq: 223
kind: "fix"
components: ["rule/global-claude-md", "skill/coder-core"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_sign_offs_stay_in_the_decision_log_and_out_of_code"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/CLAUDE.md` (and its opencode link `AGENTS.md`): "Record each sign-off with who and when" now says only in the plan's decision log (eng-spec's `03-decisions.md`, or the plan's `## Plan Deviations` line for a moved phase), never in code, comments, fixtures or commit messages.
- `claude/.claude/skills/coder-core/SKILL.md`: the private-workflow ban adds the user's name and sign-offs (who and when).
- Closes the queue item sign-off-rule-puts-the-user-s-name-in-code.

## Evidence

- The rule named no place, so coders wrote the user's full name and the date into docstrings and comments as attribution.
- Related: on 2026-10-23 the user objected to sign-off records that quote them. No user prompt about the name in code was found, so this is a fix, not a user rule.

## Result

- The new guidance test checks both texts.

## Watch

—

## Back-out

Revert the commit. The rule again names no place for a sign-off.
