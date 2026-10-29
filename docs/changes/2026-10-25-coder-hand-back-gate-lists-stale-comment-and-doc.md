---
type: "Change"
change_type: "changed"
title: "Coder hand-back gate lists stale comment and doc lines"
description: "The coder's hand-back gate on every plan phase runs stale_prose.py, which lists the comment and doc lines that name a symbol the diff renamed, removed or changed, so the coder fixes stale prose before review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T16:25:49-05:00"}
seq: 6
kind: "structured"
components: ["agent/coder", "skill/code", "agent/code-reviewer"]
evidence: ["gate ranking", "census"]
watches: ["stale-prose-handback-docs-findings", "stale-prose-handback-severe-findings", "stale-prose-handback-coder-cache-read"]
proof: ["2026-10-25-stale-prose-hand-back-check-with-a-value-only"]
overlap: "The review-findings watches read docs and bug/correctness classes only; the earlier open watches on that metric read all classes or test classes. The cache-read watch shares its metric with the earlier coder-gate and sibling-suite watches, whose readings land before this edit's after-window; read this one against its own before-window."
---

## Change

- New script `claude/.claude/scripts/code/stale_prose.py`, with helpers in `claude/.claude/scripts/lib/source_text.py`.
  It diffs the working tree against `--base`, finds each symbol whose declaration changed, and lists every comment and
  doc line that names it. For a symbol whose declaration differs only in its literals, it lists only lines that hold
  an old literal as a whole word. It exits non-zero when it lists a line, so the gate returns the list to the coder.
- `code_step.py start` appends `python3 <scripts>/code/stale_prose.py --base <base commit>` to the gate commands of
  every plan-phase coder step. Planless starts and closing phases keep no gate.
- Tests: `tests/scripts/test_stale_prose.py`, `tests/scripts/test_source_text.py`, and the gate test in
  `tests/scripts/test_code_step.py`.

## Evidence

- Work logs: docs is the largest reviewer-finding class (1626 findings in the newest intake, dotfiles and agent-evals
  sessions excluded), with 19 docs escapes.
- Bench: a sealed round of 8 runs per arm on a planted phase cut stale lines left from 12.1 to 3.4 of 15 and Opus
  reviewer fix findings from 12.6 to 3.75 per change, with no still-true line edited, no wrong rewrite and every
  hidden test passing. An earlier round without the value-only filter edited still-true lines in 7 of 8 runs.

## Result

Shipped on the branch `feature/stale-prose-handback`. Expected cost: about 175k more Sonnet cache read, 7k cache
write and 3.7k output per coder step.

## Watch

- `stale-prose-handback-docs-findings`: docs findings per code-reviewer run, good down.
- `stale-prose-handback-severe-findings`: bug and correctness findings per run, good flat.
- `stale-prose-handback-coder-cache-read`: coder Sonnet cache read per dispatch. A rise is the expected price; keep
  the edit on WORSE here while the docs watch reads BETTER, and revert if the docs watch reads NO CHANGE or WORSE.

## Back-out

Remove the stale-prose append from `start_phase_coder` in `code_step.py`; the script can stay unused.
