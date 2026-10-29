---
type: "Change"
change_type: "changed"
title: "The review-loop stop gate writes the reviewer run rows"
description: "The review-loop stop gate writes one kind=run row for each reviewer the loop dispatched, with the finding count read from the reviewer's report. Before, the loop agent wrote these rows from its own prose, and it skipped or mixed them up."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:03:31-05:00"}
seq: 9
kind: "behavior"
components: ["script/review-loop-gate", "skill/review", "agent/review-loop"]
evidence: ["census", "tests"]
watches: []
---

## Change

- `scripts/review-loop-gate.py`: on a stop that passes with no background dispatch open, it writes one run row per reviewer dispatch through `log-review-finding`. It counts the top-level entries in each finding section of the report. A none marker counts 0. A report it cannot count gets `n_findings` null. It writes each dispatch once, keyed by tool use id.
- `skills/review/log-review-finding`: accepts `n_findings=null`.
- `agents/review-loop.md`, Step 7b: the loop writes only the per-finding rows. The gate writes the run rows, so each reviewer dispatch gets one run row, not two. This edit must ship in the same commit as the gate.

## Evidence

Census over 475 review-loop transcripts on this machine: the count reads 98.4% of code-reviewer reports, 98.9% of smell-reviewer reports and 84.1% of test-reviewer reports. The rest get null: API-error stops, agents that never reported, and reports whose finding count is not clear. The count skips code fences and accepts a none marker only as a whole line, so it guesses less and reads fewer test-reviewer reports.

## Result

Staged 2026-10-21 in the script fix batch. 28 tests pass. Installed 2026-10-21.

## Watch

None yet. The run rows are the denominator of the review watch metrics, so a fuller count moves those metrics without a behavior change. After the first intake, compare run rows per review loop with the dispatch count in `agent-usage.jsonl`.

## Back-out

Restore the previous `review-loop-gate.py` and `log-review-finding` from the dotfiles history, and restore the run-row text in Step 7b.
