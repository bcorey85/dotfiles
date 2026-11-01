---
type: "Change"
change_type: "fixed"
title: "A typed user approval lets an amend pass the git-discipline gate"
description: "An amend the user approves in a prompt they type now runs: git-discipline-gate reads the user's newest typed prompt and lets `git commit --amend` pass when a sentence opens with an order to amend, holds no negation and is not a question. A peer message, a task notification, a tool result, pasted text or the agent's own text never approves one, and a force push in the same command stays denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T20:59:31-05:00"}
seq: 414
kind: "fix"
components: ["script/git-discipline-gate", "script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::GitDisciplineGateTest::test_an_amend_the_users_newest_typed_prompt_approves_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

- git-discipline-gate reads the hook input's `transcript_path` when a command holds `git commit --amend`. It finds the
  user's newest typed prompt and lets the amend pass when one sentence of it orders the amend: it opens with `amend`,
  after an optional assent (`yes`, `yeah`, `ok`, `okay`, `sure`, `fine`, `please`, `go ahead and`, `then`, `now`),
  and goes on to what to amend or ends. The sentence holds no negation (`no`, `not`, `never`, `don't`, `stop`, `without`, `hold off`, any `n't`) and does not end
  in `?`. Quoted code is dropped first, so "make the gate block `--amend`" or "amend is banned" approves nothing.
- Only a prompt the user typed counts. A meta record, a peer or cross-session message, a task notification, a
  subagent record, a compaction summary, a tool result and assistant text are skipped. Text inside `<pasted_content>`
  and `<system-reminder>` blocks is dropped from the prompt before the check.
- The approval holds until the user types their next prompt. A peer message or task notification that arrives later
  does not end it.
- A force push in the same command (`--force*`, a `+refspec`, a short-flag cluster with `f`) is denied even with the
  approval.
- The deny text names the approved path: ask the user to approve the amend in a prompt they type.
- The typed-prompt reader moves out of review-commit-gate into `lib/user_prompts.py`, which both gates use. It now also
  skips a record that starts with `<task-notification>`.

## Evidence

judgment: the gate denied an amend the user had asked for in the session, so the agent made an extra commit or handed
the user the command.

## Result

The named test fails before (every amend denied) and passes after. Companion tests keep the amend denied for a prompt
that does not order it, negates it, is a question, talks about it or only mentions it in the past tense, a later typed prompt without
it, each record the user did not type (peer, cross-session, task notification, sidechain, compaction summary, tool
result, assistant text, pasted content, system reminder), a missing transcript, and an approved amend chained with any
force-push form.

## Watch

None. A wrong pass or deny shows in the session that hits it.

## Back-out

Revert `user_approved_amend`, `is_force_push`, their constants and the amend branch of `run` in
`git_discipline_gate.py`, and the new tests. `lib/user_prompts.py` can stay as review-commit-gate's reader.
