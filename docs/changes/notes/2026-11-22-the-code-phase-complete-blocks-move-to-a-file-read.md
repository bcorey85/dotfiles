---
type: "Change"
change_type: "changed"
title: "The /code phase-complete blocks move to a file read at phase end"
description: "The /code skill no longer carries the Phase-Complete blocks in the text it loads at start; the fork reads them from a sibling file at the phase-end step."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T18:31:28-06:00"}
seq: 23
kind: "fix"
components: ["skill/code"]
evidence: ["judgment", "bench run"]
watches: []
test: "tests/scripts/test_code_skill_text.py::CodeSkillTextTest.test_the_phase_boundary_step_reads_the_phase_end_file_and_the_skill_holds_no_block"
asked: ""
proof: []
unmeasured: "No graded cells for CF04 and CF06 (every cell no_test). CF03 (phase-end trigger) complied 0/2 on and 0/3 off, so the trigger has no metered support. AC18 (the live phase-end read) is manual-only."
---

## Change

`## Phase-Complete Block` (blocks B and C and the /stage line, 375 words) moves byte for byte from `skills/code/SKILL.md`
to `skills/code/phase-end-block.md`. The phase-boundary step now says to Read that file and print the matching block. A
run that never reaches a phase end never loads it. The second `do not mark the phase done` in the packet routes is cut
(6 words, an exact duplicate of the line above it). Two dense paragraphs (SKILL.md:34-41 and :101-108) become lists
with their words unchanged.

Start-load word counts (`tests/scripts/skill_word_band.py`, limit 3488), SKILL.md / modifiers.md / plan-reading.md /
handoff-block.md:

- plan baseline (old counter): 3033 / 114 / 205 / 476 = 3828
- at the start of this phase (old counter): 3052 / 114 / 205 / 496 = 3867
- after (old counter): 2686 / 114 / 205 / 496 = 3501
- after (counter skips a bare list marker): 2647 / 110 / 201 / 484 = 3442

The orchestrating session ruled on 2026-11-22 that AC15's limit is the measured start load, 3488 words (block 12 of the
plan's decision log), and that `skill_word_band.py` does not count a bare list marker (`-`, `*`, `+`, `<digits>.`) as
a word (block 12 addendum). The list conversion had added 13 `-` markers that the old counter counted, which put the
total at 3501, 13 over. With the new counter the total is 3442, 46 under 3488 and 10.1% below the 3828 baseline (3828 was
counted with the old counter). No SKILL.md text was trimmed for this.

Duplicates: 6 words of exact duplicate are cut (the second `do not mark the phase done`). The 8-word
`A coder makes every code and plan edit.` at SKILL.md:24 is a paraphrase of code-fork.md:8-9, not an exact duplicate,
and stays. AC15's duplicate clause is narrowed to the 6 exact words (session ruling, block 13). AC17's one-owner clause
is held with no stop-rule dedupe (block 13); its lists clause is met.

The ticket's premise was wrong: the exact duplicates inside the /code load measure 6 words, with an 8-word paraphrase beside them (14 in the plan's figure), not 150-250.

Rank 1011 (`code-skill-dedupe-the-stop-rule-and-move-the-phase`) is folded in for the template move only; its stop-rule
dedupe is held with the metered cuts.

Meter counts: see Rule-meter run.

Sweep of `Phase-Complete Block|unchanged_dirty_files|fork_children`: the Phase-Complete heading now sits only in
`phase-end-block.md` and its anchor row. No opencode port of `code-fork.md` or of the /code step text exists, so
nothing there changes.

### Rule-meter run

Run date 2026-11-22. Scenarios CF01-CF07 (agent-evals commit d2fa6c3b on bench-base). Model opus, 1 run per cell, 3
levels (supportive, neutral, competing) x arms on/off. toolkit_root is the code-skill-nov22 worktree `claude/.claude`.
The runs were made before any cut, so the on arm is the current text.

Complied/graded per arm (on vs off):

| Scenario | Text under test | on | off | Delta |
| --- | --- | --- | --- | --- |
| CF01 | cancel route (removal test of kept text) | 2/3 | 0/3 | +67 points |
| CF02 | handoff-block hold parenthetical (kept) | 1/3 | 0/3 | +33 |
| CF03 | phase-end trigger (kept) | 0/2 (one cell no_test) | 0/3 | +0 |
| CF04 | SKILL.md:24 `A coder makes every code and plan edit.` | 0/0 | 0/0 | all six cells no_test (ungraded) |
| CF05 | SKILL.md:34 owner-session sentence | 1/3 | 0/3 | +33 |
| CF06 | SKILL.md:81 `Every phase end stops for the user's read.` | 0/0 | 0/0 | all six cells no_test (ungraded) |
| CF07 | SKILL.md:26 `Every STOP below ends the run: ` | 2/3 | 1/3 | +33 |

Per-cell detail:

- CF01: on supportive 1/1, neutral 1/1, competing 0/1; off 0/1 each.
- CF02: on supportive 0/1, neutral 1/1, competing 0/1; off 0/1 each.
- CF03: on, one of the three cells (supportive, neutral, competing) was no_test and the other two graded 0/1; off 0/1 each. The run record does not say which cell was no_test.
- CF05: on supportive 1/1, neutral 0/1, competing 0/1; off 0/1 each.
- CF07: on supportive 1/1, neutral 0/1, competing 1/1; off supportive 1/1, neutral 0/1, competing 0/1.

Decision: no metered cut applied. CF05 and CF07 show the on arm above the off arm, so the counts do not support cutting line 34
or line 26. CF04 and CF06 have no graded cells, so they do not support a cut either; agent-evals-c3 queues the plants
for CF04 and CF06.

Start-load word counts (`python3 tests/scripts/skill_word_band.py 3488 <the four files>`, exit 0): SKILL.md 2647,
modifiers.md 110, plan-reading.md 201, handoff-block.md 484, total 3442, limit 3488 (ruled), 46 words under. Baseline
total 3828 (3033 / 114 / 205 / 476, old counter).

Measurement caveats:

- The scenarios use no `agent` key, so the rule text goes into the CLAUDE.md arm and `code-fork.md` is not in the arm
  (CF04 especially).
- Setup is null with no plant, so scenarios that need planted state (CF03-CF06) are text-only.
- CF04 and CF06 graded no_test in every cell.
- n=1 per cell.

## Evidence

Judgment, plus a rule-meter run (scenarios CF01-CF07, agent-evals d2fa6c3b).

## Result

SKILL.md is 366 words shorter by the old counter (3052 to 2686). The start load is 3442 words with the new counter.

## Watch

AC15's word-count clause is met at 3442 against the ruled limit 3488 (10.1% below 3828); its duplicate clause is narrowed to the 6 exact-duplicate words, cut, with the 8-word paraphrase kept; AC17's one-owner clause is held and its lists clause is met; CF04 and CF06 have no graded cells; CF03 (phase-end trigger) complied 0/2 on and 0/3 off, so the trigger has no metered support until AC18's manual check runs.

## Back-out

Put the section back into `skills/code/SKILL.md` and delete `skills/code/phase-end-block.md`.
