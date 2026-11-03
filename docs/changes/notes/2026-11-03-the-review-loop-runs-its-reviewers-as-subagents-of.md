---
type: "Change"
change_type: "changed"
title: "The /review loop runs its reviewers as subagents of the main session"
description: "A reviewer launched as `claude -p` named 1 to 3 of 25 known bug lines per pass at medium effort, against 6 to 8 as a subagent of an interactive session. The scripted loop that /review launches now hands each review round to the main session, which dispatches the reviewers with Agent; the loop control, the coder and the closure calls stay in the script."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T00:02:59-06:00"}
seq: 1
kind: "structured"
components: ["skill/review", "script/review-fix", "script/review-loop-script"]
evidence: ["catch bench", "tests"]
watches: ["review-scripted-loop-cache-read"]
test: "tests/scripts/test_reviewer_dispatch.py"
asked: ""
proof: ["2026-11-03-scripted-review-loop-s-reviewers-dispatched-as"]
unmeasured: ""
overlap: "none"
---

## Change

`review_fix.py launch` starts `review_loop_script.py --reviewers main` as a detached process and writes its pid. When
a round needs reviewers, the loop writes each reviewer's prompt to a file and the round's manifest to
`reviewer-requests/round-<n>.json`, then waits for the report files. `launch` (and later `reviewer_dispatch.py wait`)
returns at that point with `ACTION: dispatch-reviewer` and one line per reviewer. `/review` dispatches each listed
agent with Agent, writes each final text verbatim to its report file, and runs `wait` again until the loop finishes.
The loop parses each report as it parsed the headless reply, and logs a call row with `via: main` and no token count.

The call infrastructure (`claude_call` and the call log) moved to `review_loop_calls.py`, so the loop script stays
under 1000 lines. `/code`'s launcher keeps headless reviewers (the default `--reviewers headless`).

## Evidence

The proof finding: a bench of the live first-round reviewer over 12 sealed phases (25 keyed bug lines), 8 passes per
arm, one blind Sonnet-graded pool. Same model, effort, prompt and tree in both arms; only the launch differs.

## Result

Keys named as fixes: main-session dispatch median 6.5 of 25 (55/200, Wilson 95% [0.216, 0.343]); headless launch
median 4 (33/200, [0.117, 0.225]). Nit-only medians 1.5 and 1. Median reviewer tokens per call rose from 141k to 279k
cache read and from 4.6k to 7.8k output; the dispatching root adds about 2k output per round.

## Watch

`review-scripted-loop-cache-read`: the reviewers' tokens now land in the main session's usage, not the loop's rows.

## Back-out

Drop `reviewers=REVIEWERS_MAIN` from `command_launch` and the dispatch-reviewer paragraph from `/review` step 1.
