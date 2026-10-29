---
type: "Change"
change_type: "changed"
title: "The coder's core skill now requires a report line for each read of the code that sets a field"
description: "The coder's core skill now makes the read of the code that sets a field owe a report line (15 more words, 653 in all)."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 14
kind: "behavior"
components: ["skill/coder-core"]
evidence: ["seeded round"]
watches: []
---

## Change

The coder's core skill now makes the read of the code that sets a field owe a report line (15 more words, 653 in all). In the block that checks the plan against the code, the sentence that said to also read the code that sets a value left. In its place: for each existing field that the new code branches, matches, parses, or computes on, find the code that sets it, and put one `SET BY` line in the report, with the file and line or the words "never assigned". The two coder agent files did not change.

## Evidence

seeded round

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Check the plan against the code it names` (evidence: seeded round):

Open the definition of what the plan describes, find the code that sets each field your code computes on and owe one `SET BY` report line for it, and flag a difference even when a workaround exists. On two planted mismatches between the plan and existing code, the coder flagged most runs with the block and few without it, and most unflagged runs shipped a defect that passes every held-out test. The owed line replaced a plain instruction to read that code. Where the mismatch shows only in the code that sets the field, the coder looked in every run with the line and in fewer than half without it, and it flagged nearly every run against fewer than half. No block appeared on a clean tree, and the line costs no tokens there. The block costs about a quarter more coder tokens on a clean phase. A flagged run leaves the affected part unbuilt, and some such runs drop the plan's fields from the types. A later seeded round with the live text showed no such run, and the cause of the fall is not known.

## Result

On two planted mismatches that show only in the code that sets a field, with no hint at the field's definition, the coder looked for that code in every run with the owed line and in fewer than half without it. It flagged the mismatch in nearly every run with the line and in fewer than half without it, and silent defects fell from most runs to one run in eight. No line came without a read behind it, and the line about the planted field was true in every run. On a clean tree no block appeared with either text, every run passed every held-out test, and the median coder tokens were equal. On the planted trees the coder took about a sixth more tokens, nearly all of it cache reads, and about half more on the tree where no run looked without the line. That is the cost of the read and the flag: without the line, a run that looked cost about 1.7 times a run that did not. The lines add about 100 tokens to each coder report. About one line in twenty named a wrong line number, and nothing checks them. Open: the line forces the read of the code and not of the plan's claim, and the one run that read the code without a flag never opened the plan lines that state the field's format. About one flagged run in three leaves plan fields out of the types, with either text, so more flags bring more such runs. A later seeded round with the live text showed no such run among its flagged runs, and a sentence that tells the coder to keep the plan's types whole gave no gain there. The cause of the fall is not known, so this item is parked until a live session shows it again. The edit changed the trigger words and added the owed line at once, so the evidence does not say which of the two carries the gain.

## Watch

—

## Back-out

—
