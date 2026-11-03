---
type: "Change"
change_type: "fixed"
title: "code runs its review rounds' reviewers as fork subagents"
description: "/code's scripted review loop hands each round's reviewers to the /code fork, which runs them as its own subagents, in place of headless claude -p reviewers; the two-round cap stays the script's."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T07:29:15-06:00"}
seq: 2
kind: "fix"
components: ["script/code-review-start", "script/code-wait", "script/reviewer-dispatch", "skill/code"]
evidence: ["bench round", "census"]
watches: ["code-review-over-cap-rounds", "review-over-cap-rounds"]
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_finding_open_after_round_two_dispatches_no_third_round"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_review_start.py` starts `review_loop_script.py` with `--reviewers main` and writes the loop's folder to
`<git dir>/code-phase/loop-dir`; `--detach` drops a stale one first. `code/code_wait.py review` now also returns when
the loop asks for reviewers: it prints `ACTION: dispatch-reviewer`, one line per open request (from
`reviewer_dispatch.request_lines`, split out of `dispatch_lines`), and the wait commands. `code_wait.py agent <id>
--report-file <file>` writes the finished reviewer's report to the request's report file, since the code-fork has no
Write tool; a reviewer with no report writes nothing and exits 1. /code SKILL.md step 5 dispatches each listed
reviewer with Agent, waits on each with `agent --report-file`, then runs `review` again.

The queue item asked to move /code onto the script's two-round cap. /code has run `review_loop_script.py`
(`while loop.iter_count < ROUND_BUDGET`) since 2026-10-31. Of 53 round-3+ rows from work repos since 2026-10-27, 47
predate that move. The 6 on 2026-11-02 are `disposition=ask` resolution rows that /code and /review log with the
packet's `iter`, which a closure or stale-prose repair pass raises to 3 with no reviewer round; no code-reviewer `run`
row past round 2 exists after 2026-10-31. The open gap was the reviewer path: /code's reviewers were headless
`claude -p` calls, which the subagent-reviewer bench found catch fewer seeded bugs (median 4 vs 6.5 of 25).

/code duties the review-loop agent path did, and where each lives now: handoff block and git-built `files`
(code_review_start.py); lane and phase fields, `scope=phase` (run_loop telemetry); later-phase file guard
(LaterPhaseEditError); phase gate commands and the stale-prose pass (phase_gate_commands); full check and expected-red
(full_check.phase_check); class closure and scoped tests (walk); plan impacts, asks and packet statuses (outcome,
handback); hand-back record (record_script_dispatch); two-round cap (ROUND_BUDGET). Nothing was left on the agent.

Still on the review-loop agent: /fix, and /review when it gets a handoff block, `base=`, a file path, `+fast`/`+deep`
or `iter=`.

## Evidence

Bench onepass11: main-session subagent reviewers caught a median 6.5 of 25 seeded bugs against 4 for headless ones,
55/200 vs 33/200 in total, at about twice the reviewer tokens. Census of `review-findings.jsonl` as above.

## Result

Before: /code's reviewers ran headless. After: they run as the fork's subagents, through the same request files /review
uses since 15eab346. The cap is unchanged and now pinned by a test.

## Watch

`code-review-over-cap-rounds` (lanes code and eng-spec) and `review-over-cap-rounds` (lane none): code-reviewer `run`
rows past round 2 per review loop. Before value 0.00; any reading above 0 is a defect.

## Back-out

Revert the commit; /code's loop then runs headless reviewers again.
