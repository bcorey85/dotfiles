---
type: "Change"
change_type: "changed"
title: "One close pass replaces the four closing phases"
description: "Plans now end with one Close pass phase run by the new /close-branch skill: scripts first, four report-only reviewers in parallel on the whole branch diff, one coder that fixes every finding, a report-only gate on the fix diff, then a script-built recap. On the TLDR-1 bench it cut closing wall-clock from 44.8 to 23.5 minutes and new defects from 1.38 to 0.50 per run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T21:25:03-06:00"}
seq: 5
kind: "structured"
components: ["skill/close-branch", "skill/code", "script/plan-format"]
evidence: ["closing bench", "tests"]
watches: ["close-pass-escapes"]
test: "tests/scripts/test_plan_format.py"
asked: "ship now then watch (2026-11-04); kept on three branches: \"the savings outweight the quality on this one. 2 defects and 2 tests is fine for 30-60% savings\" (2026-11-07)"
proof: ["2026-11-07-one-close-pass-cuts-closing-tokens-36-but-fixes"]
unmeasured: ""
overlap: "none"
---

## Change

New skill `/close-branch`. `closing-phases.md`, `plan-format.md` and the eng-spec spec template now write one
`Close pass` phase in place of Refactor pass, Test audit, Verify pass and Recap. `plan_format.py` maps a `Close pass`
title to `/close-branch`; the four old mappings stay, so a plan written with the old phases runs them as written.
`/code`'s all-phases-complete line points at the Close pass recap. `/verify-branch`, `/refactor`, `/test-audit` and
`/branch-recap` stay installed for direct use.

## Evidence

The proof finding: three sealed branches, 8 runs per arm each, four closing phases against the close pass, same
model and effort.

## Result

Pooled over three branches: all tokens 13.20M → 8.51M (−36%), Opus tokens 5.83M → 3.98M, wall-clock 51.1 → 21.3 min,
new defects 1.42 → 0.96 per run. Key defects fixed 7.25 → 6.50. The cost in quality sits on the largest branch (12
feature phases): 10.62 → 8.50 fixes per run and 6.88 → 9.25 lost tests. On the TLDR-1 branch the close pass mostly
missed one low-severity broker-call fix (6/8 → 1/8). The user ruled the token and time savings worth that loss on
2026-11-07.

## Watch

`close-pass-escapes`: review escapes per review run stay flat. A WORSE reading reverts this change. Closing
wall-clock has no intake metric and goes unmeasured in real work.

## Back-out

Restore the four closing phases in `closing-phases.md`, `plan-format.md`, the spec template and `/code`'s
all-phases-complete line. The `Close pass` mapping and the skill can stay.
