---
type: "Change"
change_type: "fixed"
title: "subagents cannot kill a process by name, pattern or job spec"
description: "wait_loop_gate denies pkill, killall, and kill with any target that is not a literal pid or $! when the Bash call comes from a subagent."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T23:29:25-06:00"}
seq: 1
kind: "fix"
components: ["script/wait-loop-gate"]
evidence: ["session"]
watches: []
test: "tests/scripts/test_wait_loop_gate.py::WaitLoopGateTest::test_subagent_kill_by_pattern_or_job_spec_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

`claude/.claude/scripts/gates/wait_loop_gate.py` gained a rule 6. When the hook input carries `agent_id`, it denies these calls:

- `pkill` or `killall`, in any form.
- `xargs kill`.
- `kill` with a target that is not a positive literal pid or `$!`. That covers a `%job`, a `$VAR`, a `$(pgrep …)` or backtick substitution, `0`, a negative process group, and a call with no target.

`kill -l` passes. Words are read through `shell_command.resolved_command_words`, so the check sees through `sudo`, `timeout` and `env`. The deny message reads: kill only a pid you started and recorded, by its number.

Only `agent_id` marks a subagent for this rule. The Claude Code hooks docs say `agent_type` is also present in a main session started with `--agent`, and the main session keeps today's behavior.

The gate's bare `except: pass` now writes the error to stderr with the gate's name, and the comment says the gate fails open.

No new hook process was added. wait_loop_gate already runs on every Bash call, is already scoped to subagents, and already polices the same `sleep` shapes the reviewer was trying to clean up. shell_write_gate (977 lines) would have crossed the 1000-line limit.

## Evidence

During a /code close pass, a reviewer subagent ran `pkill -xf "sleep 30"`. That pattern can match a process from another session on this machine: a lock holder, or another session's run. Queue item: `reviewer-pkills-processes-it-did-not-start`.

## Result

The new deny test failed before the change (13 subtests) and passes after it, along with the pass tests for a literal pid and for the main session or `--agent` seat.

Gate median wall time (40 runs each, through `sh tools/hook-python`, subagent payload):

| call | before | after |
|---|---|---|
| bare `python3 -c pass` | 7.8 ms | 8.1 ms |
| `pkill -xf "sleep 30"` | 17.3 ms | 18.1 ms |
| `kill %1` | 17.5 ms | 17.5 ms |
| `kill 1234` | 17.6 ms | 18.0 ms |
| `make test` | 17.3 ms | 17.8 ms |

The change is within noise, at about 0.5 ms. `shell_command` was already loaded through `shell_statements`.

## Watch

—

## Back-out

Revert the gate's rule 6 (`kill_reason` and its call in `subagent_reason`).
