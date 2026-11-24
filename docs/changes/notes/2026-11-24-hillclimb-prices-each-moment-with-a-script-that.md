---
type: "Change"
change_type: "added"
title: "hillclimb prices each moment with a script that sums its blocks"
description: "A new moment_price script sums one moment's blocks, from a session export or a live session's ledger rows, into one line of calls, minutes and tokens by model and type; hillclimb calls it once per moment and pastes that line on each Queued and Skipped candidate, ordering the lists by it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T11:59:47-06:00"}
seq: 1
kind: "structured"
components: ["skill/hillclimb", "script/moment-price"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-23-hillclimb-pricing-rule-raises-priced-moments-from"]
unmeasured: "The rule-meter script arm on the HC02 and HC03 fixtures has not run yet; the branch stays off master until it does."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `scripts/tools/moment_price.py`: `price <export> <first>-<last>` sums an export's block range; `price --session
  <id> --since <ts> --until <ts>` sums the session's `otel_api_request` rows in that window. Both build one block list
  and share one summing function. `check <export>` parses a whole export and stops on any line outside the grammar.
  `--json` prints the same totals as JSON. A ledger that cannot be read stops with the command that reads it, never
  a zero price.
- `scripts/lib/iso_time.py`: ISO timestamp parsing and the ledger's UTC millisecond form; `lib/human_turn_lookup.py`
  now uses it. `scripts/CLAUDE.md` names it as the owner of that fact.
- `skills/hillclimb/SKILL.md`: price each moment with one script call and paste its line on the candidate's report
  line; the report orders candidates by tokens from that line.

## Evidence

The prose pricing line priced 27-28% to 42-45% of candidate lines on the two retro fixtures, and only 1 of 18 reports
priced three quarters of its lines (finding 2026-11-23-hillclimb-pricing-rule-raises-priced-moments-from).
Tests: `tests/scripts/test_moment_price.py`, `tests/scripts/test_iso_time.py`. `check` parsed 2 of 2 real fixture
exports (18 and 17 blocks).

## Result

Pending: the script arm must price at least 75% of candidate lines in 8 of 9 reports per fixture.

## Watch

None until the meter result lands.

## Back-out

Revert the commit; the skill falls back to listing moments without a price.
