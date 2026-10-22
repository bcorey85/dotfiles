---
type: "Change"
title: "A plan phase can be marked moved to another ticket"
description: "The plan grammar accepts `- [-] Phase <id>: … moved to <KEY>` with a Plan Deviations line that records the move. code-step never runs a moved phase, and verify-branch lists it as moved, not as done or missing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:51:54-05:00"}
seq: 4
components: ["script/plan-format", "script/code-step", "script/verify-common", "script/verify-log", "script/script-utils"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/plan_format.py`:
  - A Phase Status line with `[-]` is a moved phase. It is not done and not open.
  - The line must say `moved to <KEY>`, or parse fails with `moved-without-target`.
  - The `## Plan Deviations` section must hold one line that names the phase (`Phase <id>` or `P<id>`) and the key, or parse fails with `moved-without-deviation`. The check finds the words only. It does not judge who signed.
  - A moved phase needs no `## Phase <id>` section.
  - New `moved_phases(text, name)`.
- `scripts/script_utils.py`: the markdown heading regex moves here as `MARKDOWN_HEADING`. New `heading_section_indexes`, which skips fenced lines.
- `scripts/code-step.py`:
  - Phase picking uses `open`, so `start` never picks a moved phase.
  - `start --phase <id>` on a moved phase stops and names the ticket.
  - If a phase becomes moved while its coder runs, the after-coder step stops and says that the work is not marked done or committed.
  - The plan-complete text and the last-phase text name the moved phases.
- `scripts/verify_common.py` and `scripts/verify-log`: Manual Verification items of a moved phase are not listed as owed. The packet gets a "Moved phases" section with each phase, its ticket and its count of unchecked items.
- Tests: `test_plan_format.py`, `test_script_utils.py`, `test_code_step.py`, `test_verify_branch_script.py` under `tests/scripts/`.

## Evidence

- Work incident: a plan moved one phase to a follow-up ticket with the user's sign-off. The plan grammar accepted only `[ ]` and `[x]`, so `[-]` failed as an unparsed line. The hook's suggested fix, `[ ]`, marked the phase as open, which was false.

## Result

A plan can record a moved phase in its own grammar. The run and the branch-end check skip it, and the move needs a written record in Plan Deviations.

## Watch

None. No intake metric counts moved phases or plan-format failures by kind.

## Back-out

Restore the previous `plan_format.py`, `script_utils.py`, `code-step.py`, `verify_common.py` and `verify-log` from git. A plan that already uses `[-]` then fails to parse.
