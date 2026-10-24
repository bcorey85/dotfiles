---
type: "Change"
title: "Split code_step into four modules; hand-backs read from the event log"
description: "code-step reads every hand-back from one record with one match rule, its hooks no longer write the state file, four unused edge cases are gone, and no function in it is over complexity 10."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T11:54:36-05:00"}
seq: 9
kind: "behavior"
components: ["script/code-step"]
evidence: ["census", "judgment"]
watches: []
test: ""
unmeasured: "The change keeps every verb, route and printed ACTION text. The cut branches had no sighting in any session, so no intake number reads them. The gain it aims at is fewer code-step fix lanes, which no intake stream counts."
---

## Change

`code_step.py` is split into `code_step.py` (the verbs), `code_step_core.py` (state, event log, hand-back matcher, output), `code_step_boundary.py` (criteria guard, verification runner, phase boundary) and `code_step_hooks.py` (the hook entry points). Imports run one way. Pure plan helpers moved to `plan_format.py`. `run_process` (run a command, kill its process group on a timeout) is in `script_utils.py`.

Hand-backs: one record and one match rule. The waiting verbs read the newest `handback` event in the run's event log from the agent that the open dispatch launched. `reports.jsonl`, the coder-row filters and the handback-store fallback are gone. The handback store is read only for the review packet.

The PreToolUse hook on `SubagentHandback` logs every attempt as a `handback-attempt` event, so a PLAN-IMPACT in a hand-back that a gate denied still reaches the user; the wait still ends only on a hand-back that went through. An asks round reads only the coders of its newest dispatch. An Agent launch with no agent id is logged, and the waiting verb stops on it at once.

Hooks only log events. The resumed-agent flip moved into the waiting verb, and the fork deny and stop-block counts became events. This removes the unlocked write race between the hooks and the verbs on `state.json`.

Removed, with no sighting in any session: `--take-over` and the live-owner stop, the addendum coder, the branch-switch and missing-plan stops in `after-plan-edit`, and the long-checks fresh-call wait. The criteria-guard restore stays. `git_output` returns stdout only.

`tests/run.sh` fails the run on C901 over 10 in the five files.

## Evidence

Census: a fix census of code-step since 10-19 found 8 normal-path fixes, 7 one-sighting edge cases and 6 with no sighting. Its 11 functions over complexity 10 took 3.6 commits each, against 0.6 for the rest. Judgment: a complexity review of the whole module chose the record and the cuts.

## Result

- Non-blank, non-comment lines in the code-step modules and `plan_format.py`: 3125 to 3294 (+5%). The four modules alone: 2759 to 2824, and 104 lines moved into `plan_format.py`. Functions: 225 to 289, from the C901 splits. The line target was not met: the cuts paid for the splits, the hand-back attempt log and the newest-dispatch filter, but no more.
- C901 hits over 10: 13 to 0.
- State keys read or written: 80 to 70.
- Hand-back records: 4 with two match rules, to 1 with one.

## Watch

None; see `unmeasured`.

## Back-out

Restore `code_step.py`, `plan_format.py`, `script_utils.py`, `tests/run.sh` and the tests from the commit before this change, and delete the three new modules.
