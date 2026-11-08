---
type: "Change"
change_type: "changed"
title: "review and fix run in a sonnet fork that dispatches the reviewers"
description: "/review and /fix run in the Sonnet code-fork, which launches the script loop detached, dispatches the reviewers as its own subagents, runs the packet, and hands back one stop that the Opus main session relays word for word."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T22:10:48-06:00"}
seq: 12
kind: "structured"
components: ["skill/review", "skill/fix"]
evidence: ["judgment"]
watches: ["review-fork-main-cache-read", "fix-fork-main-cache-read"]
test: ""
asked: ""
proof: ["2026-11-03-scripted-review-loop-s-reviewers-dispatched-as"]
unmeasured: ""
---

## Change

`skills/review/SKILL.md` and `skills/fix/SKILL.md` set `context: fork`, `agent: code-fork`, `model: sonnet`. The shared steps live in `skills/_shared/review-fork-run.md`: the run folder, heredoc writes of the findings, handoff and `review-stop.md`, `review_fix.py launch --detach`, the reviewer dispatch and `code_wait.py review --loop <loop dir>` waits, the packet's ACTION lines read as STOPs, and `resume` handling (asks-done `--by user`, `decide discuss`). `review_launch.py` takes `--detach`; `code_wait.py review` takes `--loop <folder>` and prints the packet command when the loop ends. `code_relay.py` relays the newer of `stop.md` and `review-stop.md`, and a stop with no `To go on:` line gets a rule that lets a calling skill (`/cc` after `/fix`) go on. `agents/code-fork.md` names all three skills. The reviewers stay subagents.

## Evidence

judgment: work intake 2026-11-07 put the old review-loop agent at 0.72M (/review, 66 runs) and 0.76M (/fix, 49 runs) against 2.38M (10 runs) and 3.15M (8 runs) since main dispatched the reviewers itself; the /code fork already moved the same dispatch work off the Opus main session. The reviewers stay Agent subagents, as the 2026-11-03 finding on subagent against headless reviewers measured; the fork's cost is unmeasured until the watches read.

## Result

`test_code_wait.py`, `test_code_relay.py` and `test_review_fix_script.py` pass with new tests for `--loop`, `--detach`, the review stop and the finished-stop rule.

## Watch

`review-fork-main-cache-read` and `fix-fork-main-cache-read`: Opus main-session cache read per /review and per /fix turn, down.

## Back-out

Restore the two skills' frontmatter and bodies, delete `skills/_shared/review-fork-run.md`, and revert `--detach`, `--loop` and the `review-stop.md` relay.
