---
type: "Change"
title: "Run the 19 shell hooks as Python scripts"
description: "19 hooks written in bash now run as Python scripts with the same decisions and output. batch-reads-nudge points straight at its Python file. At work, each bash hook takes 110–470 ms per call because bash and every program it starts are slow to launch there. Python starts in 13 ms. The predicted cut is about 0.5 s of hook time per Bash call at work."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T07:40:45-05:00"}
seq: 1
components: ["script/shell-write-gate", "script/quality-check-cap", "script/git-discipline-gate", "script/review-commit-gate", "script/comment-bloat-gate", "script/stale-citation-gate", "script/dead-prose-gate", "script/claudemd-linecount", "script/calibration-refs-guard", "script/spec-budget-gate", "script/test-edit-telemetry", "script/agent-model-guard", "script/agent-foreground", "script/log-agent-usage", "script/log-skill-use", "script/format-changed", "script/emit-orchestration", "script/calibration-guard", "script/warn-skip-hooks", "script/batch-reads-nudge", "script/claude-doctor", "skill/review"]
evidence: ["census"]
watches: ["hook-port-python"]
---

## Change

19 new scripts in `scripts/`, one per bash hook, plus a shared module `scripts/hook_input.py` that reads the hook input. Each `.py` file makes the same decision and prints the same output as its `.sh` file. They use only the standard library and parse under Python 3.7.

The `settings.json` registrations of the 19 hooks change from `<dir>/<name>.sh` to `python3 <dir>/<name>.py`. The `batch-reads-nudge` registration changes from the `.sh` wrapper to `python3 <dir>/batch-reads-nudge.py`, the file the wrapper ran. The old `.sh` files stay installed as the back-out.

The three generated security gates (`bash-safety-gate.sh`, `block-credential-read.sh`, `write-edit-safety-gate.sh`) do not change.

Two callers move to the `.py` names. The invocation-log check in `skills/review/review-scope-check` runs `python3 <dir>/log-skill-use.py`. `scripts/claude-doctor.sh` looks for the `.py` registrations of `log-skill-use`, `emit-orchestration`, `shell-write-gate` and `quality-check-cap`, so it stops its false warnings after the swap.

The `pi` and `omp` agent configs in dotfiles also call the ported hooks by their `.py` names. `pi/.pi/agent/settings.json` runs them with `python3`. The `omp` bridge `claude-security-bridge.ts` runs a `.py` name with `python3` and the generated gates with `bash`.

Two outputs change on purpose:

1. `comment-bloat-gate` treats a `-` the way the fixed rule intends.
2. When a file cannot be opened or the input is not JSON, the stderr text names the hook, in place of bash's or jq's own text. Exit codes do not change.

## Evidence

census

The work hook timing census ran each registered hook 10 times with a Bash `ls` payload:

| Hook | Work median, ms | Home median, ms (bash / Python) |
|---|---|---|
| quality-check-cap, before the call | 447–469 | 23.9 / 28.7 |
| quality-check-cap, after the call | 347–349 | 23.9 / 28.7 |
| shell-write-gate | 245–340 | 19.0 / 20.5 |
| review-commit-gate | 263–295 | 10.0 / 13.8 |
| git-discipline-gate | 128–132 | 8.3 / 22.6 |
| bash start, no profile | 40 | |
| python3 -I start | 13 | |

The hooks before a Bash call run in parallel and took 425 ms at work. The hooks after it took 338 ms. Bash and each program a bash hook starts cost 10 to 40 ms at work, and a bash hook starts several. A Python hook starts one process.

At home, the Python hooks are slower than the bash hooks by 1 to 19 ms each, because Python starts slower there than bash.

## Result

Parity on real hook inputs from this machine, with the same decision, stdout and exit code:

- 15 hooks match on every input, for example shell-write-gate 2000/2000, review-commit-gate 4000/4000 and git-discipline-gate 2856/2856.
- quality-check-cap 3994/4000. The 6 differ only in the state-file name, which hashes the test root. Stdout and exit codes match.
- comment-bloat-gate 1986/2000. The 14 are the intended `-` change.
- claudemd-linecount 341/343. The 2 are the intended stderr text.
- format-changed 1999/2000. The 1 is a file that changed in the live repo during the run.

354 port tests pass against the new scripts.

Predicted at work: the hooks before a Bash call drop from 425 ms to about 120–150 ms. `bash-safety-gate.sh` (114–123 ms) then sets the floor. The hooks after the call drop from 338 ms to about 30–60 ms.

Work hook timing census, 2026-10-20, against 2026-10-19 (10 runs each, payload `ls`, parallel hook group):

| Hook group | Before | After |
|---|---|---|
| Before a Bash call, median | 425 ms | 139 ms |
| Before a Bash call, max | 566 ms | 184 ms |
| After a Bash call, median | 338 ms | 39 ms |
| Main session, sum of medians before a call | 1396 ms | 420 ms |

Both groups match the prediction and stay under 200 ms. `bash-safety-gate.sh` is now the slowest hook at work, 158–179 ms. Live hook durations at work run 10 to 20 times the census values: `batch-reads-nudge` took 1.3–2.2 s per run on 2026-10-19 and 2026-10-20. The work machine showed a load average of 17.6–20.6.

## Watch

`hook-port-python`: the daily median of subagent short Bash reads at work, before against after 2026-10-20. The good direction is down, by about 0.5 s. The next work hook timing census gives the direct reading: the parallel hook group times before and after a Bash call. If either group stays above 200 ms, read the per-hook table for the slow port.

Reading, 2026-10-26 intake: WORSE, kept. The subagent short-read median went from 1.54 s before to 4.75 s after. The rise started a week before this edit: 1.6 s on 2026-10-12, 2.3 s on 10-14, 3.3 s on 10-19, then 4.6 s on 10-20. The main session rose the same way. Calls a hook rejected, which run no command and no classifier, rose from 0.5 s to 1.7 s before the edit and kept rising after it. `batch-reads-nudge` took 76 ms per run on 2026-10-04 and 1.4 s on 10-19 as a bash hook. As a Python hook it took the same 1.3–1.6 s. The work machine showed a load average of about 16 on 10 cores, with a Docker VM at 617% CPU and 73 days of uptime. The machine slows every call, so this metric cannot read the edit. The direct census reading stands: the hooks before a Bash call fell from 425 ms to 139 ms, and the hooks after it fell from 338 ms to 39 ms. The watch is closed.

## Back-out

Restore `settings.json` from `settings.json.bak-hookport`, if no other edit came after the swap. Otherwise change each `python3 <dir>/<name>.py` registration back to `<dir>/<name>.sh`. The `.sh` files are still installed.
