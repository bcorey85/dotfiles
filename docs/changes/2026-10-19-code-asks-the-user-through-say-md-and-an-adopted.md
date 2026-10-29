---
type: "Change"
change_type: "changed"
title: "/code asks the user through say.md, and an adopted plan change gets a plan-edit coder before the review"
description: "/code writes every question for the user into say.md. When the user adopts a plan change, a coder rewrites the contradicted plan steps before the review, so one disagreement gets one question and one review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-19T08:42:34-05:00"}
seq: 8
kind: "behavior"
components: ["skill/code", "script/code-step"]
evidence: ["bench run"]
watches: ["code-one-question-per-plan-disagreement"]
---

## Change

`code-step.py` writes every question for the user into `<git dir>/code-step/say.md` and prints `ACTION: ask-user`. The forked subagent cannot ask the user, so the main session asks the question from the hand-back. This applies to the plan question, the review asks, and the plan lookup questions. The `present-asks-and-wait` action is removed.

When the user adopts a plan change, the script first dispatches a coder that edits only the plan file. That coder rewrites each step, verification command and success criterion that the adopted change contradicts. A new verb, `after-plan-edit`, then starts the review. If the plan coder changed any file other than the plan, the script adds the file to the review and flags it.

Other fixes in the same script:

- The review packet parser drops the `|` indicator and the indent of a block value.
- A resumed run (`decide`, `asks-done`, `verify`) clears say.md first, so an old summary does not reach the user again.
- The behavior sentence of the coder goes on a file only when exactly one file changed. Before, every file got the same sentence.

`skills/code/SKILL.md` step 2 says that `ask-user` means: run any command the output names, then hand back. Step 4 says that the hand-back is say.md verbatim.

## Evidence

bench run

### Anchor reasons

Anchor `skills/code/SKILL.md`, section `# Code` (evidence: bench run):

The subagent runs the routing script and does what each ACTION line says. Every question for the user is in say.md, because the forked subagent cannot ask the user, and the main session asks it from the hand-back. In one bench plan run, the old text asked the same plan disagreement 2 times. The cause was that an adopted change left the contradicting plan step in place, so the next review found the same conflict. That cost about 21 minutes and a second full review.

## Result

Bench plan run on the old script: one plan disagreement was asked 2 times. The end state was green, with 310 tests. The run found 6 script defects: the `|` indicator in the question, an AskUserQuestion instruction that the skill forbids, no say.md text on one question path, say.md never cleared, the contradicting plan step left in place, and one behavior sentence on every file.

The patched script passes 10 of 10 new checks, and the original fails 7 of them, at least one per defect. The standing suite, updated for the new question path, passes 66 of 66.

A live bench rerun on the fixed script asked the conflict once. A coder made 4 edits to the plan and to no other file before the review. Full review loops fell from 3 to 2, and main-session wall-clock fell from 3,680 s to 2,540 s. Opus reviewer cache read stayed about the same, 8.54M against 8.34M, because the second review came from an accepted review ask. The end state was green, with 307 tests.

## Watch

review escapes per review run. The work log holds only 2 plan-disagreement rows, too few for a rate, so the watch shares the review-escape reading of the forked-router change.

## Back-out

Restore `skills/code/SKILL.md` and `scripts/code-step.py` from git.
