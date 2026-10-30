---
type: "Change"
change_type: "security"
title: "An orchestrator's pane prompts are marked, and it never answers a worker's question for the user"
description: "herdr-phase-change prefixes a plain-text prompt with the sending pane, and orchestration.md forbids typing an answer to a question put to the user into another session's input box."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T22:30:00-05:00"}
seq: 295
kind: "fix"
components: ["script/herdr-phase-change", "rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_phase_change.py::HerdrPhaseChangeTest::test_a_plain_prompt_goes_out_marked_with_the_sending_pane"
asked: ""
proof: []
unmeasured: "Whether an orchestrator given the line still types an answer into a worker's pane."
---

## Change

- `herdr-phase-change`: a prompt that does not start with `/` goes out as
  `[from orchestrator pane <sending pane id>] <prompt>`. The pane id comes from `herdr-api pane current`; when it
  cannot be read, the script sends nothing and exits 1. `/clear` and slash-command prompts go out byte for byte.
- `orchestration.md`: never submit text in another session's input box to answer a question put to the user; tell
  the user to answer in that pane.

## Evidence

- An orchestrator typed an approval into a worker's input box to answer a question the worker had put to the user.
  The worker took it as the user's answer.
- Slash prompts stay unmarked. A leading marker turns `/clear` or `/code ...` into plain text, so the command never
  runs, and an appended marker lands in `/code`'s arguments as brief text. The risk is a plain-text answer typed
  into a worker's box, and the marker covers every plain-text prompt.
- `herdr-dev` types the launch command into a shell pane it just created, and `clip-image` types a path into its own
  pane. Neither sends to another session's input box, so neither is marked.

## Result

- The marking test and the no-sending-pane test fail before the change and pass after. A slash-prompt test pins the
  byte-for-byte send. The orchestration guidance test fails before the line and passes after.

## Watch

—

## Back-out

Revert the commit.
