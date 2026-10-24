---
type: "Change"
title: "Toolkit edits need a bench proof sized by task class"
description: "From 2026-10-25 a change file's kind is fix, user-rule, structured or open; structured and open must cite findings with 8 or 32 runs per arm, and a dotfiles pre-commit hook refuses a toolkit commit with no change file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T17:48:13-05:00"}
seq: 18
kind: "behavior"
components: ["method/bench", "method/protocol"]
evidence: ["user rule", "census"]
watches: []
unmeasured: "it gates the ledger and dotfiles commits on this machine, which no work intake reads; the ledger itself shows whether change files carry proof"
---

## Change

From 2026-10-25, `build_changes.py` accepts four kinds and refuses `behavior`. A `fix` names a test, as before. A `user-rule` quotes the user's words and date in `asked`. A `structured` change (agent behavior on a task with a checkable answer) names in `proof` findings with `task_class: structured` and `runs_per_arm` of 8 or more. An `open` change (planning, design or research judgment) needs `task_class: open` and 32 or more. `build_findings.py` validates the two new finding keys. A new `~/dotfiles/.githooks/pre-commit` refuses a commit that stages a file under `claude/.claude/` agents, skills, commands, hooks or scripts, or its `CLAUDE.md`, without a staged change file, and refuses any commit while the ledger fails its check.

## Evidence

user rule, census

The user asked that toolkit edits be proven before they ship, with a classification by task. Of the 122 change files dated 2026-10-10 to 2026-10-24, 32 rested on judgment or a census alone, and most bench rounds behind the rest ran 3 runs per arm. Published work on agent eval reliability finds run-to-run agreement settles at 8 to 16 trials on structured tasks and needs 32 or more on complex reasoning.

## Result

338 change files and 417 findings pass the new checks. 30 ledger tests and 8 hook tests pass; the dotfiles suite ran 1,961 tests with 0 failures.

## Watch

None: see unmeasured.

## Back-out

Restore `bin/build_changes.py` and `bin/build_findings.py` in agent-evals from git, delete `~/dotfiles/.githooks/pre-commit` and its test, and unset `core.hooksPath` in dotfiles.
