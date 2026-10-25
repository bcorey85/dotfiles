---
type: "Change"
title: "Fail the toolkit test run on new duplicate code"
description: "tests/run.sh now runs tests/duplicate_code.py, which fails when a toolkit script defines a top-level function name another script already defines, or when jscpd finds a new token clone; today's repeats sit in a baseline that may only shrink."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T16:11:30-05:00"}
seq: 6
kind: "user-rule"
components: ["script/duplicate-code", "script/parallel-tests"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-25: we also probably need jscpd to block future duplicate code issues"
proof: []
unmeasured: ""
---

## Change

`tests/duplicate_code.py` runs two checks over `claude/.claude/scripts`, `claude/.claude/hooks` and each skill's
own `scripts/` folder. The vendored skills under `skills/synced/` stay out.

- Same name: a top-level Python function defined in two or more files fails, `lib/` included. `main`, `check`,
  `run` and `decide` are hook and command entry points and may repeat.
- Token clones: `npx jscpd@4.0.5` at its default thresholds, Python and bash. A new file pair, or more clones in a
  listed pair, fails. Without npx the clone check is skipped with a note, as `run.sh` skips ruff.

`tests/duplicate_code_baseline.json` lists today's repeats: 29 function names and 14 clones in 9 file pairs. An entry
that no longer holds also fails, until `tests/duplicate_code.py --shrink` drops it. `--shrink` never adds an entry.

`tests/run.sh` runs the check after lint and before the unit tests. `ruff.toml` lints the new script.

## Evidence

The user asked for it during the git_output merge. Measured on the tree before that merge: jscpd at its default 50
tokens found none of the six git_output copies, which were 3 to 9 lines with different bodies. At 12 tokens it found
1 of the 6 among 147 clones. The same-name rule flagged all 6. So jscpd alone does not stop the copied-helper class;
both checks ship.

## Result

`bash tests/run.sh` with a copy of `git_output` planted in `gates/`: exit 1, naming the function and both files.
Without it: exit 0, 2059 tests in 55 files, 0 failed. The check adds about 1.3 seconds once npx has cached jscpd.
ruff is not installed on this machine, so lint was skipped locally. Tests:
`tests/scripts/test_duplicate_code.py`, 9 tests.

## Watch

None. No intake number reads duplicate code in the toolkit; the baseline size is the reading.

## Back-out

Revert the commit.
