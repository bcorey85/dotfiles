---
type: "Change"
change_type: "changed"
title: "code-step logs each dispatch to an event log and denies a coder launch without its packet"
description: "code-step writes each dispatch, launch, resume and hand-back to one event log per run, saves each dispatch prompt to a file that ends in a marker line, and a new PreToolUse hook denies a launch whose prompt does not hold the whole saved prompt."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T19:55:39-05:00"}
seq: 23
kind: "behavior"
components: ["script/code-step", "script/script-utils"]
evidence: ["work incident", "transcript read", "tests"]
watches: []
---

## Change

- Each run gets a `runId` and a log at `<git dir>/code-step/runs/<runId>/events.jsonl`. Each dispatch writes a `dispatch` event and a `prompt-<id>.txt` file. The printed prompt ends with the line `code-step-dispatch: <runId>/<id>`, and the output adds a `PROMPT FILE:` line.
- New `code-step.py log-hook` (PostToolUse, matcher `Agent|SubagentHandback|SendMessage`) writes `launch`, `resume` and `handback` events. It reads the agent id from `tool_response.agentId` only, and prints one stderr line when that field is missing.
- New `code-step.py dispatch-hook` (PreToolUse, matcher `Agent`) denies an Agent call of the open dispatch's agent type when the saved prompt is not in the call's prompt. The reason tells the caller to read the prompt file and pass its whole text. After 3 such denials, it tells the caller to stop and tell the user. It also denies a second coder launch that carries the same marker.
- The three hooks share one setup helper with the session filter. `pre_tool_use_deny` moves into `script_utils.py`.
- Every verb still decides from `state.json` and `reports.jsonl`, and waits as before. The switch of reads to the log, and a reprint of an unlaunched prompt, come in a later change after one real run shows that the log hook fires.
- The hook entries come as a patch to `settings.json`, applied with `git -C ~/dotfiles apply`.

## Evidence

Work incident: code-step ties a hand-back to its dispatch by comparing times across two stores. A coder that still ran got an `ask-user`, a plan edit returned the next dispatch while the coder ran, and a review loop resumed by SendMessage did not re-register.

Transcript read: in three /code sessions on one day, the subagent piped `code-step.py start` through `head` or `sed`. The coder packet was cut and never sent. No hook checked the coder prompt.

Tests: the lane suite passed 442 tests. The new tests feed hook events captured from local transcripts through log-hook. Each of five planted faults in the new hooks failed the test meant to catch it. Every new test fails against the installed code.

## Result

Built 2026-10-21 after two fix rounds and a clean code and test review. Waits for the install and the settings patch.

## Watch

None. No intake metric counts coder dispatches without the packet. The next check is one real /code run that shows `dispatch`, `launch` and `handback` events in the log.

## Back-out

Reverse the settings patch with `git -C ~/dotfiles apply -R`. Then run the commands in the install backup's `RESTORE.txt`.
