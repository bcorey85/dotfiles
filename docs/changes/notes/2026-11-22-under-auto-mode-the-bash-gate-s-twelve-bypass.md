---
type: "Change"
change_type: "changed"
title: "Under auto mode the Bash gate's twelve bypass-guard rules and the inline interpreter hint log and pass (pilot)"
description: "A two-week pilot on this machine: in an auto mode session the twelve shape rules of the Bash gate and the inline interpreter hint record the command and let it go on to the gate's other rules and the auto mode classifier, and the sudo rule stops matching the word inside quoted search text."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T12:06:36-06:00"}
seq: 14
kind: "user-rule"
components: ["script/bash-safety-gate", "script/inline-interpreter-hint"]
evidence: ["user request", "removal round", "census"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "The pilot runs on this machine only, and the work intake reads work logs. Its reading is local: agent-evals gate_pilot/beta_report.py, read weekly for two weeks against the bars in gate_pilot/README.md."
---

## Change

Two installed files change; `agent-evals/gate_pilot/pilot.py install` writes them and `restore` puts the archived
ones back.

- `scripts/bash-safety-gate.sh`: when one of twelve rules matches (inline interpreter, stdin interpreter, `sh -c`,
  `eval`, `exec`, `source`, `xargs`, `find -exec`, `awk system`, `sed e`, here-string to a shell, credential-pattern
  search) and the call's `permission_mode` is `auto`, the gate appends a row to
  `~/.claude/security-hook-shadow-log.jsonl` and does not block. The command still passes through every later rule.
  It blocks as before in any other mode, when `jq` is missing, when the row cannot be written, or when
  `~/.claude/security-pilot-off` exists.
- The same file's `sudo` rule reads the command with quoted text blanked. `rg -n "sudo" notes.md` was blocked and now
  passes; `sudo ls` and `bash -c "sudo ls"` are still blocked.
- `scripts/gates/inline_interpreter_hint.py`: under the same conditions it writes a shadow row and passes in place
  of denying with its script-file hint.

No new hook process: both checks sit inside hooks that already run on every Bash call.

## Evidence

- census: the twelve rules made 2,042 of this machine's 2,445 Bash gate blocks in 14 days (84%), and 803 of 946 at
  work (85%).
- removal round: without the twelve rules the gate blocks 14 of 123 hand-labelled harmless commands where it
  blocked 122, and 0 of 40 seeded harmful commands reach the shell in either arm
  (`agent-evals/findings/2026-11-22-dropping-the-bash-gate-s-twelve-bypass-guard-rules.md`).
- user request: the user signed off on the change and asked for the pilot.

## Result

Built and checked; installed by the user's command.

- Differential check, 399 commands through the archived and the pilot gate: in default mode 3 verdicts change, all
  quoted-`sudo` searches; in auto mode 155 change, each a twelve-rule block that passes or is caught by a later rule;
  with the off switch set, auto mode matches the archived gate. Verdicts outside those allowed changes: 0.
- 24 pilot tests pass. The toolkit suite, run against a staged tree that holds the two pilot files: 177 of 179
  test files pass (5,236 tests). The two that fail are not from this change: the rule-anchor check on prompt files
  other open sessions were editing, and a test file another session deleted during the run. The four hook test
  files pass again on the final pilot build.
- Hook time, median of 30 runs, bare bash start 1.2 ms, bare Python start 10.2 ms:

| Bash call | Archived gate | Pilot gate | Archived hint | Pilot hint |
| --- | --- | --- | --- | --- |
| `ls -la` | 15.6 ms | 16.6 ms | 37.6 ms | 39.5 ms |
| `git status --short` | 18.5 ms | 17.7 ms | 38.2 ms | 36.5 ms |
| `python3 -c 'print(1)'` | 36.7 ms | 105.5 ms | 39.5 ms | 41.1 ms |
| `ls \| xargs touch` | 77.4 ms | 80.4 ms | 29.8 ms | 27.3 ms |

A command that matches no rule costs the same. A command the archived gate blocked at its first match now runs
through the rest of the rules, so the inline interpreter case goes from 36.7 ms to 105.5 ms; that call was a block
and a retry before.

## Watch

None in the intake: see `unmeasured`. The local reading is `gate_pilot/beta_report.py`: blocks by the twelve rules
per day before and since, and a hand read of every passed command that ran.

## Back-out

Build 2 of the pilot replaces this build in the same two files and moves 36 more rules: see
`2026-11-22-under-auto-mode-48-of-the-bash-gate-s-69-rules-log.md`. This build is kept under
`agent-evals/gate_pilot/versions/gate-pilot-1-cc42eb333a15/`.

`touch ~/.claude/security-pilot-off` turns the pilot off at once. `python3 ~/agent-evals/gate_pilot/pilot.py restore`
puts the two archived files back.
