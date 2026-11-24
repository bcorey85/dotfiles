---
type: "Change"
change_type: "changed"
title: "Plan-format rules split into one-branch bullets and the design-decision format folds into the decision step"
description: "Three dense plan-format paragraphs become one bullet per rule, the criterion-test sentence is reworded, and the single-loader design-decision-format file folds into eng-spec's decision step. The rules carry over except five clauses the fold drops: the evidence rule's trigger (a change to what an external tool accepts or enforces at runtime), the Reasoning field's \"reference the user's input where the user decided\", \"a rejection that names no failure mode is unsupported\", \"Can't name a killed option → no fork existed\", and the definitions of the `exercised` and `declared-only` evidence classes."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T18:34:40-06:00"}
seq: 35
kind: "structured"
components: ["shared/plan-format", "skill/eng-spec", "script/spec-budget-gate"]
evidence: ["prompt audit"]
watches: []
test: ""
asked: ""
proof: ["2026-11-22-the-eng-spec-emoji-heading-line-is-followed-8-of-8"]
unmeasured: "plan-format splits of the phase-0/skeleton paragraph, the Automated Verification shapes paragraph and the Expected-red/File paragraph; the reworded criterion-test rule; the spec-template declared-only line; the 5-decisions fold, including the heading form and the scope-only-rejection sentence it carries over. The budget gate test pins the new file list. The PF01 and PF02 rule text is not in this branch's plan-format, so no worktree copy of them exists."
---

## Change

- `plan-format`: the Phase 0 / walking skeleton paragraph, the Automated Verification paragraph (three shapes, the rg ban and presence rule, the wrapped-search rule, the must-end-by-itself rule) and the Expected-red / File paragraph each become one bullet per rule. The closing criterion-test sentence now reads "A test covers a criterion by its behavior, never by a marker ... No mocks inside such a test."
- `eng-spec` decision step 13 carries the four-field block format, the no-table rule, the constraint rule, the scope-only-rejection sign-off and the credentials rule. `_shared/design-decision-format.md` is deleted.
- `spec-template`: the External Contracts comment carries the declared-only rule from the deleted file.
- `spec_budget_gate`: `SHARED_FILES` drops the deleted file; its test's expected totals follow (`~8701 words`, `currently 7100`).

## Evidence

Rule-meter worktree copies ES01W and ES02W (the 5-decisions emoji-heading line, unchanged by this edit) run against this branch's `5-decisions.md`: each scenario at each of three prompt levels, 8 runs per arm on the default model: 8 of 8 complied with the rule on, 0 of 8 with it off. This proves the worktree-copy mechanism. The reworded and split text has no scenario: see `unmeasured`.

## Result

ES01W 8/8 on, 0/8 off in every prompt-level cell (24/24 and 0/24 overall); ES02W the same. Anchors check passes; no anchor row covers the three edited files. No file outside the gate and its test named the deleted file; the opencode ports hold no copy.

## Watch

None: the rule-meter arms cannot grade the split and reworded text, so it is listed as unmeasured.

## Back-out

Restore `design-decision-format.md` from git, put its name back in `SHARED_FILES`, and revert the test's expected strings.
