---
type: "Change"
change_type: "changed"
title: "Retire branch-recap; close-branch holds the one recap template"
description: "The branch-recap skill and its opencode command are deleted; close-branch Step 6 now holds the companion-branches step, and the Recap closing phase names /close-branch."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-27T20:03:39-06:00"}
seq: 6
kind: "user-rule"
components: ["skill/close-branch", "skill/branch-recap"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-27: the user asked sessions to burn down the toolkit queue while away; the orchestrating session ruled this item retire, not legacy"
proof: []
unmeasured: "No intake number reads the recap skill's use; this removes a duplicate skill."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- Deleted `claude/.claude/skills/branch-recap/SKILL.md` and `opencode/.config/opencode/commands/branch-recap.md`.
- `claude/.claude/skills/close-branch/SKILL.md`: the companion-branches step moved into Step 6.
- `claude/.claude/skills/_shared/closing-phases.md`: the Recap closing phase names /close-branch.
- Stale references removed from the todos and test-audit skills, `skills/audit/review.md`, `scripts/tools/resolve-task-dir.sh`, `scripts/telemetry/log-scan`, `scripts/lib/plan_format.py` and `docs/agent-evals.md`.
- Tests updated: test_guidance_rules, test_plan_format, test_review_fixes, test_telemetry_switch.

## Evidence

Judgment: two skills held a recap template, so a change to one left the other stale.

## Result

One recap template, in close-branch. No reference to branch-recap remains in the files above.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit; the skill, the opencode command and the old references return.
