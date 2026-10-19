---
type: "Change"
title: "Deny unbounded waits in subagent Bash calls"
description: "A new PreToolUse Bash hook denies a subagent's wait that has no time limit: an until or while loop with sleep, a long for loop with sleep, follow-mode log reads, and a sleep over 30 s. The deny reason gives the counted-loop form. At work, these waits ran to the 10-minute Bash ceiling and took about 4.3 hours of agent time over 3 days."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-19T16:42:38-05:00"}
seq: 11
components: ["script/wait-loop-gate"]
evidence: ["census"]
watches: ["wait-loop-gate"]
---

## Change

New script `scripts/wait-loop-gate.py`, registered as a PreToolUse hook on Bash in `settings.json`. It acts only when the hook input shows a subagent (`agent_type` or `agent_id` is set). The main session is exempt. `CLAUDE_SKIP_HOOKS` turns it off.

It denies four shapes:

1. An `until` or `while` loop that runs `sleep`.
2. A `for` loop that runs `sleep`, unless its count is a literal and count × sleep is 120 s or less.
3. Follow mode: `tail -f`, `docker logs -f`, `docker compose logs -f`, `kubectl logs -f`, `journalctl -f` and `watch`. A call that starts with `timeout N`, where N is 120 or less, is allowed.
4. A standalone `sleep` over 30 s.

Each deny reason gives the bounded form `for i in $(seq 30); do <check> && break; sleep 3; done`. It tells the agent to stop waiting and report a check that still fails in its hand-back.

The script ignores heredoc bodies, quoted strings and comments. It uses only the standard library and starts no subprocess. Any error exits 0 with no output.

## Evidence

census

The phase-time intake covered 9 work repo blocks over 3 days. In the long coder runs, Bash took about 300 minutes and the model about 77. The largest part was waits with no time limit that ran to the 10-minute Bash ceiling:

| Run | Agent | Calls at the ceiling | Minutes |
|---|---|---|---|
| Main checkout, one day | coder | 16 `until` loops and 2 `docker logs` follow calls | about 151 |
| Second ticket worktree | coder | 6 `until` loops | 44.5 |
| Third ticket worktree | general-purpose | 5 `until` loops | 40.3 |
| Fourth ticket worktree | coder | 2 `until` loops | 18.1 |

The ceiling calls had a median of about 600 s. Each one waited for a condition that did not come true, so the full 10 minutes was lost. A counted loop with a 120 s total stops about 8 minutes sooner on each such wait.

## Result

17 tests in `~/dotfiles/tests/scripts/test_wait_loop_gate.py` pass against the installed path. They cover each denied shape, the allowed bounded forms, heredoc and quote stripping, the main-session exemption and the skip variable. The full dotfiles suite passes, 99 tests.

Expected saving: about 4 hours over 3 days of work runs, if the agents use the bounded form. The work-machine result is not in yet.

## Watch

`wait-loop-gate`: subagent Bash calls per day that ran 590 s or more, from the work intake, before against after 2026-10-20. The good direction is down. If the count does not drop, or the coders' hand-backs start to report waits they gave up on too early, revisit the 120 s limit.

## Back-out

Remove the `python3 ~/.claude/scripts/wait-loop-gate.py` entry from the PreToolUse Bash block in `settings.json`, then delete `scripts/wait-loop-gate.py`.
