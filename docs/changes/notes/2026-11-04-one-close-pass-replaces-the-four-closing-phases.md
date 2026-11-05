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
asked: "ship now then watch (2026-11-04)"
proof: ["2026-11-04-one-merged-close-pass-halves-closing-wall-clock"]
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

The proof finding: TLDR-1, 8 runs per arm, four closing phases against the close pass, same model and effort.

## Result

Wall-clock 44.8 → 23.5 min. All tokens 10.82M → 9.13M (−16%, short of the 33% bar). Cost $8.13 → $6.42. Key
defects fixed 5.50 → 5.25. New defects 1.38 → 0.50. Two fixes the close pass found less often: F2, the low-severity
unguarded broker call in the import task's finally (6/8 → 1/8), and F3, the medium dispatcher reschedule on a DB
error (3/8 → 0/8). One branch only; the rerun on TLDR-3 and TLDR-4 is queued.

## Watch

`close-pass-escapes`: review escapes per review run stay flat. A WORSE reading reverts this change. Closing
wall-clock has no intake metric and goes unmeasured in real work.

## Back-out

Restore the four closing phases in `closing-phases.md`, `plan-format.md`, the spec template and `/code`'s
all-phases-complete line. The `Close pass` mapping and the skill can stay.
