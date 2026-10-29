---
type: "Change"
change_type: "changed"
title: "The complexity reviewer's prompt now holds its contract only"
description: "The complexity reviewer's prompt is now its contract only: the role line and its one question, the calibration inherit, the module bound with the diff-only refusal, the five deletable shapes with every example, the three oracle clauses, the magnitude floor."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 3
kind: "behavior"
components: ["agent/complexity-reviewer"]
evidence: ["removal round"]
watches: []
---

## Change

The complexity reviewer's prompt is now its contract only: the role line and its one question, the calibration inherit, the module bound with the diff-only refusal, the five deletable shapes with every example, the three oracle clauses, the magnitude floor, the cost clause and the tests-are-the-contract rule, the four suppressed classes, the three deferrals, the format line, the four process steps with the reference-count requirement, and the output block (945 words, was 1,122). Gone: fourteen sentences that explained why a rule exists, none of which named a shape, a gate, a search, or an output field.

## Evidence

removal round

### Anchor reasons

Anchor `agents/complexity-reviewer.md`, section `(preamble)` (evidence: removal round, judgment, census, seeded round):

Frontmatter and the role line with its one question. The opus pin and the whole-module depth paragraph, changed together: on the seeded module, three runs, Opus caught all five shapes in every run, where Sonnet caught the branch-table pair in 1 of 3 and the repeated guard in 0 of 3. On the clean twin Opus filed 1 to 2 findings per run against 0 to 1, with a median of 1 against 0. Gone: "Not what repeats, not what is misnamed, not what is buggy. What is _unnecessary_." Three of five seeded shapes were found in every run of both wordings; the other two were missed equally. Gone later: the project memory line of the frontmatter, which had no effect while auto memory is off in the settings. The description is a routing line: what the agent is, who dispatches it, and any rule that the dispatcher needs. A census of this machine's top-level dispatches, a guide only, found none that menu text alone picked, and no dropped dispatcher rule had the description as its only home.

Anchor `agents/complexity-reviewer.md`, section `## Inherit the calibration verbatim` (evidence: removal round, census):

The Read of the shared calibration file and its four section names. Gone: "Restraint binds you hardest — 'simpler' is arguable about almost any code." Every run of both wordings read the file; the unseeded module drew zero findings in three of three full-text runs and two of three cut-text runs, the third a below-floor finding. Those runs held a fifth name for the memory section. That name left when the memory section was removed.

Anchor `agents/complexity-reviewer.md`, section `## Your bound` (evidence: removal round):

Module bound, diff-only refusal, pre-existing code is the target. Gone: "you cannot answer your question from a diff" and "Recency is irrelevant here".

Anchor `agents/complexity-reviewer.md`, section `## Your scope — the five deletable shapes` (evidence: removal round):

The five shapes with every example, the call-site rule, the reachable-handling rule. Gone: the hop-cost sentence under indirection and the "synchronization is the smell" sentence under two owners. Indirection, configurability, and two-owner plants were found 6 of 6 in both wordings; the branch-table plant 1 of 3 in each; the downstream-guard plant 0 of 3 in each.

Anchor `agents/complexity-reviewer.md`, section `## The deletion oracle (a finding without all three does not ship)` (evidence: removal round):

The three clauses with quantification examples. Gone: "you are proposing a rewrite on vibes". Every seeded finding in both wordings carried a quantity, an enabling change, and an unreachability clause.

Anchor `agents/complexity-reviewer.md`, section `## Magnitude floor` (evidence: removal round):

The ~10-lines-or-a-concept floor. Gone: "Never report a finding whose only content is that you would have written it differently."

Anchor `agents/complexity-reviewer.md`, section `## Name the cost` (evidence: removal round):

The cost clause and the tests-are-the-contract rule. Gone: "These changes touch behavior in a way duplication fixes do not", "not understood well enough to report", "it is not a simplification". Every seeded finding named a cost.

Anchor `agents/complexity-reviewer.md`, section `## Not findings` (evidence: removal round):

The four suppressed classes. Gone: the clever-table clause and "where the extension point is the product". The six decoys were filed as findings in zero runs of either wording.

Anchor `agents/complexity-reviewer.md`, section `## Explicitly NOT your scope` (evidence: removal round):

The three deferrals and the `Note:` rule. Gone: "Fully expressible as 'this repeats' = theirs; 'this need not exist' = yours."

Anchor `agents/complexity-reviewer.md`, section `## Format` (evidence: removal round):

The `[complexity]` prefix and the `[design-decision]` route. Byte-identical in both wordings. Not itself varied.

Anchor `agents/complexity-reviewer.md`, section `## Process` (evidence: removal round):

Read all, map, reference-count, confirm. Gone: "The findings come from this map, not from reading files one at a time." Every seeded indirection and configurability finding in both wordings reported a reference count from `rg`.

Anchor `agents/complexity-reviewer.md`, section `## Output Format` (evidence: removal round):

The report block and the ordering rule. Gone: "when the code is already as simple as its problem".

## Result

A Go CLI's report and render packages, seeded with one instance of each of the five shapes (two switches over one discriminator, a one-implementation interface with a factory, a sort knob every caller sets to one value, a normalization repeated downstream of the CLI's validation, report totals accumulated twice and reconciled) and six decoys that must stay suppressed, plus the unseeded packages as a clean twin; three Sonnet runs per wording per tree. Both wordings found the indirection, the knob, and the two-owner plants in every run with a reference count and a cost clause, found the switch pair in one run each, and never filed the downstream guard. Neither filed a decoy. The unseeded packages drew no finding in any full-text run and one below-floor finding in one of three cut-text runs. The cut text spent 0.94x the Sonnet fresh-plus-output tokens and made four fewer tool calls per three runs. Live gaps, report-only: the branch-table shape is caught one run in three and the downstream-guard shape never, in both wordings; the `[design-decision]` tag on an exported-type removal was applied in two of three full-text runs and one of three cut-text runs.

## Watch

—

## Back-out

—
