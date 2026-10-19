---
type: "Change"
title: "A coder never runs a whole test suite, a whole-package lint or a build"
description: "A coder never runs a whole test suite, a whole-package lint or a build."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-19T00:00:00-05:00"}
seq: 2
components: ["skill/coder-core", "agent/review-loop", "script/coder-gate"]
evidence: ["judgment"]
watches: ["coder-whole-package-check-hook"]
---

## Change

A coder never runs a whole test suite, a whole-package lint or a build. `coder-core` now tells the coder to run the typecheck, and lint and tests for only the files it changed, because the review loop runs the full check once at its end. A new PreToolUse hook on Bash, `coder-gate.py bash-hook`, refuses those commands for coder agents only, with the same reason, and logs each refusal to `~/.claude/coder-gate.jsonl` as `whole-package-deny`. It uses the same command test as `coder-gate.py set`

## Evidence

judgment

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## Verify before you report` (evidence: removal round, sealed round):

Now only: report each command with its exit code. The targeted-tests rule lives in the global CLAUDE.md. Earlier: one sentence, run the project's quality checks. What remains of the pre-submission checklist; equal on every test with the checklist gone. The one-re-run limit lives in the quality-check-cap hook. By judgment, coders now run only the tests and fast checks for their changed files and report each command with its exit code; the review loop runs the full suite once at its end. Effect unmeasured. Later, by judgment: run each check with its full output in a `/tmp/` log and never pipe it into `head`, `tail` or `grep`. One bench phase was voided when a coder cut its only check output and the cap hook denied the re-run. When the brief says that a hook runs the checks at hand-back, the coder runs none and fixes what the hook returns. In a sealed round of three runs per arm, the hook refused 1 or 2 hand-backs per run. The coder fixed each failure and handed back again, and the final gate passed in 3 of 3 runs. Arm wall rose 19% at the median, because each hook run is a full typecheck, lint and test pass. By judgment, the scope rule is back in this section: the typecheck, and lint and tests for only the changed files, never a whole suite, a whole-package lint or a build. A Bash hook in the gate script refuses those commands for coders. In the sealed round, the coders that ran their own checks ran path-scoped tests but a whole-package lint.

## Result

In the sealed coder round, the coders that ran their own checks ran path-scoped tests but a whole-package lint and typecheck. Before this edit, the coder rule named no scope, and the targeted-tests rule in the global CLAUDE.md covers tests only. A scratch test of the hook refused 19 whole-package commands for a coder, allowed the same 19 for a non-coder agent, allowed 10 scoped coder commands, and logged 19 refusals. A live `claude -p` probe with a coder agent refused `npm test` and `npm run lint`, ran `npm test -- src/a.test.js`, and logged two refusal rows.

## Watch

Sonnet coder cache read per dispatch from the weekly token table, and `whole-package-deny` rows per week in the gate log.

## Back-out

delete the `bash-hook` entry from the Bash PreToolUse list in `settings.json` and the scope sentences in `coder-core`
