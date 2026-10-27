---
type: "Change"
title: "Toolkit Python follows PEP 8 names and a full ruff rule set"
description: "The 28 kebab-case toolkit scripts get snake_case file names, camelCase identifiers become snake_case, and ruff lints E,W,F,I,N,B,UP,SIM,C4,RUF at 120 columns on every suite run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T06:39:37-05:00"}
seq: 7
kind: "behavior"
components: ["script/code-step", "script/coder-gate", "script/review-fix"]
evidence: ["user rule"]
watches: []
test: ""
unmeasured: "A rename and lint sweep changes no number that the intake reads. Hook ids in stderr and log rows keep the kebab-case form."
---

## Change

- 28 `.py` files under `scripts/` and `skills/*/scripts/` get snake_case names. `settings.json`, skills, agents, rules, tests, `run.sh`, `ruff.toml` and the rule-anchor paths name the new files.
- 808 camelCase names become snake_case, and 175 exception classes get the `Error` suffix. A syntax-tree rename did the work, not a text substitution. JSON keys, state-file keys, log fields, flags and env var names stay as they are.
- `hook_input.hook_name()` maps the snake_case file stem back to the kebab-case hook id, so log rows still join across the rename.
- `ruff.toml` selects E,W,F,I,N,B,UP,SIM,C4,RUF at line length 120. Each ignore is per file and has a comment that says why. `tests/run.sh` runs `ruff check` with that select and fails on a hit.
- `docs/toolkit-script-rules.md` names the snake_case rule for identifiers and the ruff pass before hand-over.

## Evidence

User rule: the toolkit Python must follow PEP 8. Before the sweep there were 6663 hits on the expanded rule set, with 516 camelCase assignments against 104 snake_case ones in the scripts. `ruff.toml` selected only F, so nothing checked names.

## Result

Full suite on the lane: 1973 tests, 0 failed, two runs in a row. `ruff check`: zero hits.

## Watch

None. See `unmeasured`.

## Back-out

Run the lines in the lane backup's `RESTORE.txt`.
