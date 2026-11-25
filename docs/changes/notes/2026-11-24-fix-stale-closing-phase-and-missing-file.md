---
type: "Change"
change_type: "fixed"
title: "Fix stale closing-phase and missing-file references"
description: "Prompt files stop pointing agents at retired closing phases, a routing table that is gone and a retired log file, and the test-reviewer lists every scope the review loop sends."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T21:52:32-06:00"}
seq: 7
kind: "fix"
components: ["skill/test-audit", "skill/branch-recap", "skill/escape", "skill/peer-review", "agent/test-reviewer", "agent/plan-verifier"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_rule_anchors.py::RuleAnchorsTest::test_every_prompt_block_has_a_current_row"
asked: ""
proof: []
unmeasured: "prose-only reference fixes; no intake number reads them"
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Each line is a path or fact fix under `claude/.claude/`; CUT marks a deletion.

- `skills/test-audit/SKILL.md:9`: "The third closing phase — the one test question" -> "The one test question".
- `skills/branch-recap/SKILL.md:3`: "The final closing phase — assemble" -> "Assemble"; trigger "wrap up the branch" removed.
- `skills/branch-recap/SKILL.md:9`: "The fourth and last closing phase, and the exit-side counterpart" -> "The exit-side counterpart".
- `skills/audit/skills.md:24`: CUT the clause that checks the "Workflow Routing" table in CLAUDE.md, which no longer exists.
- `skills/_shared/code-vocabulary.md:44`: CUT the sentence "`/branch-recap` re-checks at branch scope."
- `agents/test-reviewer.md:23-29`: added the `fs` scope and the "owned files" scope the review loop sends.
- `agents/plan-verifier.md:28`: CUT the paragraph "A dispatch naming `scope: phase <N>` is stale", a dispatch nothing sends.
- `skills/peer-review/SKILL.md:22`: "never log to `review-metrics.jsonl`" -> "never log review metrics" (the file is retired).
- `skills/escape/SKILL.md:14`: CUT the copied stage list; the line points at the `log-escape` header.
- `README.md:64,121-128`: the closing chain and table now name `/close-branch`, the one closing phase.

## Evidence

Census: the prompt-audit rows 2-9, 18 and 19, each rechecked against origin/master before editing.

## Result

All nine rows still held; none skipped. Done-when checks recorded by the builder session.

## Watch

None: no intake number reads these lines.

## Back-out

Revert the commit.
