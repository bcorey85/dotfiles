---
type: "Change"
change_type: "changed"
title: "claude -p agent seats skip the orchestration rules"
description: "The SessionStart hook that injects orchestration.md emits nothing when the hook input carries agent_type, so a claude -p --agent review or coder seat stops loading about 1,500 tokens of main-session rules that tell a coder seat never to code."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T01:27:46-05:00"}
seq: 309
kind: "fix"
components: ["script/emit-orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_emit_orchestration.py::EmitOrchestrationTest::test_agent_seat_input_emits_nothing"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `gates/emit_orchestration.py` reads the SessionStart hook input. A non-empty string `agent_type` (set when the
  session runs with `--agent`) means a seat: the hook prints nothing and exits 0. A main session, empty stdin,
  unreadable stdin, non-JSON input or a non-object input still loads the rules; the last three say so on stderr.
- The rules file is read through `hook_input.read_file_text` in place of the hook's own copy.
- Two fixtures hold captured SessionStart inputs, one main and one `--agent code-reviewer`, with the home path
  scrubbed.

## Evidence

- The review-loop script starts every review seat and coder seat with `claude -p --agent <name>`. At work it runs a
  median 10 model calls per run, 7 of them `--agent` seats. orchestration.md is 6,080 bytes, about 1,500 tokens, so
  each run wrote about 10,000 tokens of rules into seat caches and read them back on every seat turn.
- Seats with no `--agent` keep the rules: the review loop's disposition, check-finder and class-closure steps.
- No launcher in dotfiles starts an interactive session with `--agent`, so every session the user starts keeps the
  rules.

## Result

Targeted tests pass: a main-session input emits the rules, an `--agent` input emits nothing.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
