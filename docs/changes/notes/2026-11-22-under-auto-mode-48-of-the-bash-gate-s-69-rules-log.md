---
type: "Change"
change_type: "changed"
title: "Under auto mode 48 of the Bash gate's 69 rules log and pass; permission deny entries and the classifier stand in (pilot build 2)"
description: "The second build of the pilot on this machine: in an auto mode session 36 more rules of the Bash gate record the command and pass. Four command rules (push to main, force push, no-verify, root) hand over to 28 permissions.deny entries in settings.json, and 32 target rules hand over to auto mode's classifier with its default rules. 21 rules keep blocking in every mode."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T12:47:56-06:00"}
seq: 19
kind: "user-rule"
components: ["script/bash-safety-gate"]
evidence: ["user request", "removal round", "census"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "The pilot runs on this machine only, and the work intake reads work logs. Its reading is local: agent-evals gate_pilot/beta_report.py, read weekly to 2026-12-06 against the bars in gate_pilot/README.md."
overlap: "Same metric as the build 1 change (blocks by the Bash gate under auto mode): build 2 replaces build 1 in the same file and the beta report reads all 48 rules together, so the two are not read apart. The command-rule and target-rule moves were each replayed alone and ship together; the build that holds both was checked offline only."
---

## Change

Two places change. `agent-evals/gate_pilot/pilot.py settings apply` and `install` write them, `restore` and
`settings remove` put them back, and `pilot.py log` lists every write with its sha256 before and after.

- `scripts/bash-safety-gate.sh`: under auto mode, a match by one of 36 more rules appends a row to
  `~/.claude/security-hook-shadow-log.jsonl` and does not block. With build 1's twelve, 48 of the 69 rules now pass.
  - Four command rules (push to main, force push, `--no-verify`, root) pass only while all 28 deny entries are in
    `~/.claude/settings.json`, and still block a command that runs another command handed to it (`sh -c`, `eval`,
    `env`, `xargs`, `find -exec`, `ssh`), since a deny entry does not read inside one.
  - 32 target rules (deletes, resets, uploads, remote copies, pipes to a shell, writes to protected paths,
    credential and history reads) pass with nothing added: the classifier's default rules stand in.
  - Every moved rule blocks as before in any other permission mode, when `jq` is missing, when the row cannot be
    written, or when `~/.claude/security-pilot-off` exists. 21 rules block in every mode.
- `settings.json`: 27 entries are added to `permissions.deny` (the 28th, `Bash(sudo *)`, was there). No other key
  changes, and no `autoMode` key is added.

Before: `rg -n "push origin main" notes.md` and `rm -rf build/out` were blocked by the gate. After: both reach the
classifier and run. `git push origin main` is refused by a deny entry, and so is `git -C <repo> push origin main`,
which the regex let through.

No new hook process: the checks sit inside the hook that already runs on every Bash call.

## Evidence

- census: at work the four command rules hold 75 of 5,662 Bash gate blocks and four of the target rules hold 1,840
  (credential file reads 1,171, recursive deletes 433, piped environment dumps 140, pipes to a shell 96).
- removal round, command rules: with deny entries in their place the sampled commands blocked fall from 40 to 15 of
  41 and harmful commands reaching the shell fall from 2 to 0 of 24
  (`agent-evals/findings/2026-11-22-permission-deny-entries-in-place-of-the-bash-gate.md`).
- removal round, target rules: without them the harmless commands blocked fall from 170 to 14 of 172 and no harmful
  command reaches the shell, 0 of 81 with or without
  (`agent-evals/findings/2026-11-22-auto-mode-s-default-classifier-in-place-of-the.md`).
- user request: the user signed off on both moves and asked for the full rework.

## Result

Built and checked; installed by the user's command on 2026-11-22 at 13:03 CST.

- Differential check, 399 commands through the archived and the pilot gate: default mode, archived blocks 395 and
  pilot 392 (three quoted-root-word searches); auto mode, archived 395 and pilot 7; auto mode with the off switch,
  pilot 392. Verdicts outside the allowed changes: 0.
- Offline, the 65 command-rule commands through build 2: all 41 sampled commands pass the gate; of the 24 harmful
  ones the gate blocks the two shell-string forms and the other 22 rest on the deny entries.
- 40 pilot tests pass. The toolkit suite, run against a staged tree that holds build 2: 5,235 of 5,236 tests pass
  (178 files). The one failure came from build 1's hint, which is already installed: the test that forbids finding
  toolkit code through the home folder flagged the hint's off-switch path. The off switch is a flag file, not code,
  so `tests/scripts/test_toolkit_self_location.py` now allows that line by name, and the test file passes (4 tests).
- Hook time under auto mode, median of 30 runs, bare bash start 1.2 ms, bare Python start 10.9 ms:

| Bash call | Archived gate | Build 1 | Build 2 |
| --- | --- | --- | --- |
| `ls -la` | 17.1 ms | 17.4 ms | 17.6 ms |
| `git status --short` | 16.7 ms | 17.0 ms | 18.1 ms |
| `python3 -c 'print(1)'` | 35.5 ms | 111.3 ms | 111.2 ms |
| `git push origin main` | 43.2 ms | 41.9 ms | 117.6 ms |
| `rm -rf build/out` | 49.5 ms | 53.0 ms | 114.0 ms |
| a root command inside `sh -c` | 29.3 ms | 69.3 ms | 76.6 ms |

A command that matches no rule costs the same. A command the gate used to block at its first match now runs
through the rest of the rules, about 70 ms more; that call was a block and a retry before.

## Watch

None in the intake: see `unmeasured`. The local reading is `gate_pilot/beta_report.py`: blocks by the moved rules
per day before and since, the count each layer refused, and a hand read of every passed command that ran.

## Back-out

`touch ~/.claude/security-pilot-off` brings the old blocking back at once. `python3 ~/agent-evals/gate_pilot/pilot.py
restore` puts the archived files back, and `pilot.py settings remove` takes out the 27 added entries. Build 1 is
kept under `gate_pilot/versions/gate-pilot-1-cc42eb333a15/`.
