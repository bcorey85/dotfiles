---
type: "Change"
change_type: "fixed"
title: "asks-done records whether the user or the session ruled"
description: "The asks-done verb of review_fix.py and code_step.py takes --by user|session, each ask outcome row carries ask_decided_by, and the ask prompts tell the session to rule itself when the repo's CLAUDE.md hands it ask decisions."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T09:44:25-05:00"}
seq: 50
kind: "fix"
components: ["script/review-fix", "script/code-step", "skill/review", "script/log-review-finding"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_asks_done_by_session_logs_who_ruled_and_says_so"
asked: ""
proof: []
unmeasured: ""
---

## Change

`asks-done` in `review_fix.py` and in `code_step.py` takes an optional `--by user|session`, default `user`, the same words the `decide` verbs use. Every ask outcome row sends `ask_decided_by`. A bad `--by` value is refused and logs nothing. In `/code`, outcomes set by the pre-set outcome (runs with no user) log `session`. The `/review` present-asks text, the `/code` ask-user text and the `/review` skill line say: when the repo's CLAUDE.md hands ask decisions to the session, decide each ask and add `--by session`. The shared `pop_option` helper in `script_utils.py` takes the flag out of the argument list for both scripts.

`log-review-finding` documents `ask_decided_by`. A ledger build that refuses it with `field_unknown` gets the row without it, the same retry `snapshot` already had, now a loop over both optional fields.

Before, a headless repo either stalled on a user who was not there, or the session ruled and the row read as a user answer.

## Evidence

judgment: a headless repo whose CLAUDE.md has the session decide each ask and record it as Delegated reported that the `/review` ask step gave it no way to do that. All new tests fail on the base commit and pass after, in `test_review_fix_script.py`, `test_code_step.py`, `test_log_review_finding.py` and `test_script_utils.py`.

## Result

Full suite and ruff pass. The current ledger registry has no `ask_decided_by` field, so the ledger drops it with a note until the registry gains the field. Rows written to the local jsonl fallback keep it.

## Watch

—

## Back-out

Revert `pop_option`, the `--by` handling and `decided_by` arguments in both scripts, the prompt sentences, the `/review` skill clause, the retry loop in `log-review-finding` (back to the snapshot-only retry), and the new tests.
