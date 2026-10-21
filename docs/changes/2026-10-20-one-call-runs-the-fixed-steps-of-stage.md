---
type: "Change"
title: "One call runs the fixed steps of /stage"
description: "`stage.mjs --run` classifies once, stages the SAFE tier, writes the metrics row and prints the finished report and jump list. The model keeps only the per-entry notes, the nvim-jump call and tier disagreements."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T18:31:11-05:00"}
seq: 5
components: ["skill/stage"]
evidence: ["census", "judgment"]
watches: ["stage-run-one-call"]
---

## Change

`skills/stage/scripts/stage.mjs` gets a `--run` mode (`--no-stage` keeps the index as is):

- One classification. Before, the skill ran the classifier twice (`--json`, then `--stage`).
- It stages the SAFE tier from that classification, counts N staged and M left to read, and writes the `lane=stage` metrics row. A logging failure prints a warning and never changes the exit code.
- It prints the `## Stage` report in reading order, a `jump-queue` block (tier, path, line, reason for each entry with a line), and one line naming what the model still does.
- A classifier or git error exits 2 with "nothing staged by this run".

`skills/stage/SKILL.md` Phases 1-4 now call `--run` once. The model writes the one-line note for each jump entry, makes one `nvim-jump` call, and adds tier disagreements. It does not recompute N, M or the log row. `--json` and `--stage` work as before.

## Evidence

Census of work main sessions on Opus: /stage took 239 human turns and 1,965 model responses, median 5 per turn, 5.9% of main-session cache reads. Each response re-reads about 99k tokens of context. Judgment from the skill text: about 3.5 responses per turn were fixed steps (second classifier run, log row, counts, report layout).

## Result

`tests/scripts/test_stage_run.py`: 15 of 15 passed against the patched script. The tests cover an empty diff, deleted, renamed, space and non-ASCII paths, a bad `.stage.json`, `--no-stage`, a classifier error, a repo with no commits, not a repo, a logging failure, one classification per run, and unchanged `--json` and `--stage`. A `--run --no-stage` on the agent-evals working tree printed 6 queue entries and staged nothing.

## Watch

`stage-run-one-call`: main-session model responses per /stage turn, expected down. Before: median 5, mean 8.2. If it does not drop, the per-entry notes, not the fixed steps, carry the cost.

## Back-out

Restore `skills/stage/scripts/stage.mjs` and `skills/stage/SKILL.md` from git.
