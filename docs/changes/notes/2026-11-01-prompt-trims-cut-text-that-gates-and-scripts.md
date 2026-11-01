---
type: "Change"
change_type: "removed"
title: "Prompt trims cut text that gates and scripts already enforce"
description: "The ten most-used skills and agents load about 2,100 fewer words per call: text a hook, gate or script already enforces or prints, text repeated in the same or an always-loaded file, and pointers to readers that do not exist are cut, with every judgment rule and parsed contract kept."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:28:51-05:00"}
seq: 421
kind: "user-rule"
components: ["agent/review-loop", "agent/coder", "agent/code-reviewer", "agent/test-reviewer", "skill/coder-core", "skill/review", "skill/fix", "skill/code", "skill/cc", "skill/stage", "skill/commit"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-01: after the overnight cut-candidate report: fix everything"
proof: []
unmeasured: ""
---

## Change

Words before → after (`wc -w`):

- `skills/review/SKILL.md` 978 → 375 and `skills/fix/SKILL.md` 987 → 395: the ACTION tables go, because `review_fix.py` prints each ACTION's instruction; the model duties the script does not do stay (judge each ask's answer, append deviation lines under `## Plan Deviations`, /fix's escape-guard proposal). The intro and Modifiers sections and the saved-packet explanation go.
- `agents/review-loop.md` 5,683 → 5,120: the loop-order diagram, the second `full_check` enum, the JSON-type reminder, gate-denied plan-edit and unreviewed-coder restatements, stale and dead references, and repeated prior-issues and post-processing text.
- `skills/code/SKILL.md` 2,355 → 2,208, plus /cc, /stage, /commit and `_shared/nvim-jump.md`: duplicate step text, script-restating bullets, /commit's branch-guard step (`git_discipline_gate.py` denies a commit on main), and the unused `nvim-jump --list` line. /cc triage and resolve, the /commit secret scan and escape check stay.
- `skills/coder-core/SKILL.md` 1,554 → ~1,326, `agents/coder.md` 149 → 122, `agents/code-reviewer.md` 1,497 → 1,459: the hook-block recovery paragraph (a copy of the global CLAUDE.md rule), banned-command items gates already block, a dead pointer, and the REFACTOR CANDIDATES, `REVIEW:` and `SET BY` report lines no script reads. The ticket-id ban, extend-never-copy, red-test rules and every parsed contract stay word for word.
- `agents/test-reviewer.md`: summary and count fields no script reads.

## Evidence

A census of each file tagged every rule ENFORCED, DUPLICATE, DEAD or TEXT-ONLY; each editor confirmed the gate or script line before cutting an ENFORCED item. Only the first three classes were cut.

## Result

Full dotfiles suite: 2,923 tests in 110 files, 0 failed. Per-call savings by model: /review and /fix about 1,200 Opus-main words; review-loop, /code and coder-core about 950 Sonnet words.

## Watch

None: the intake reads no per-prompt word count, and the cut text changed no behavior a gate does not already hold.

## Back-out

Revert the commit.
