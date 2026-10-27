---
type: "Change"
title: "/code runs the review loop as a script"
description: "The /code step script launches review_loop_script.py in place of the Sonnet review-loop agent: each reviewer, coder and class-closure judgment is its own claude -p call, and scope, parsing, routing, the round cap and the full check are code."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T07:20:00-05:00"}
seq: 73
kind: "structured"
components: ["script/code-step", "script/review-loop-script", "script/format-changed"]
evidence: ["replacement bench", "tests"]
watches: ["scripted-review-loop-tokens", "scripted-review-loop-escapes"]
test: "tests/scripts/test_code_step_review_script.py"
asked: "Port the benched loop driver into /code; keep its routes, no extra reviewer; work repos get no new CLAUDE.md line."
proof: ["2026-10-26-scripted-review-loop-with-bounded-re-review-vs"]
unmeasured: ""
overlap: "The open escape watches read every review run; this one guards against a rise, and the replacement bench already fixed 10 defects to the agent's 9, so it ships before their readings."
---

## Change

- New `review/review_loop_script.py`, ported from the benched `loop_driver.py`. It writes the hand-back packet, the
  run event, the hand-back store row and the review-loop-gate stop row that the agent's hooks wrote.
- `code_step_review.emit_review_dispatch` launches the script detached and prints `ACTION: wait`. `resume` waits for
  its hand-back. A script that exits with no hand-back stops with its log and the `review-again` line. `abort` and
  `review-again` kill a running script.
- The full check comes from the repo CLAUDE.md `Quality check` line. Without one, a haiku check-finder reads the
  repo's docs, Makefile, package and CI files. If it names none, the run stops as critical-blocker before any
  reviewer.
- `format_changed.py` exits at once when `CLAUDE_FORMAT_HOOK_OFF` is set; the script sets it in its sessions.
- /review, /fix and fix-first keep the agent.

## Evidence

- LOOPSCRIPT-2 replacement bench, 12 pairs: 751K vs 1.30M median tokens (42% fewer), 217 s vs 396.5 s (45% faster),
  10 vs 9 defects fixed, 0 failed full checks.
- Check-finder trials: a pnpm+make repo gave `pnpm typecheck && make ci` (8.6 s, 25K tokens); a repo with no check
  stopped with its reason (11.8 s, 49K tokens).

## Result

- Full suite and ruff pass on the worktree.

## Watch

- `scripted-review-loop-tokens`: review-loop cache read per dispatch, down.
- `scripted-review-loop-escapes`: review escapes per review run, flat.

## Back-out

Set `CODE_STEP_REVIEW_LOOP=agent` to dispatch the agent again, or revert the commit.
