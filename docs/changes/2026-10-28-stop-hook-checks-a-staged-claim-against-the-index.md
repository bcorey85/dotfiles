---
type: "Change"
change_type: "fixed"
title: "Stop hook checks a staged claim against the index"
description: "A main session told the user files were staged without checking, so the user could commit a partial change. A new Stop and SubagentStop hook, staged_claim_gate.py, reads the final message. When a sentence says files are staged, it checks git diff --cached in the repo the sentence names, else the session cwd's repo, and blocks the stop when the index is empty or misses a file the sentence names."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T14:46:21-05:00"}
seq: 217
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::StagedClaimGateTest::test_a_staged_claim_with_an_empty_index_is_blocked"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `scripts/gates/staged_claim_gate.py`, for Stop and SubagentStop:
  - A claim is a sentence saying `is/are/were/was/now/all/been/left/remain(s)/stay(s) staged`, `I staged`, `I've staged` or `I have staged`, with no `not`, `no`, `nothing`, `none`, `never` or `committed`, and no `if`, `once`, `when`, `after`, `before`, `until` or `unless` before the claim in its own clause (clauses split at `,`, `;`, `:`, `and`, `but`, `so`). So "are staged, so review before you commit" and "Once the tests passed, I staged the fix" are still checked.
  - Known limit: a sentence that claims one file staged and also names another file it does not claim (for example the file it was edited from) is blocked when that other file is not in the index.
  - The repo checked is the repo of each existing absolute path the sentence names, else the session cwd's repo.
  - It blocks when that repo's `git diff --cached --name-only` is empty, or misses a file the sentence names that exists in the repo. The reason names the repo and the missing files, and says to run `git diff --cached --name-only` and report what the index holds.
  - A second stop in a row passes, so a session cannot spin. Any error passes silently. It only reads the index.
- `settings.json` must list it under Stop and SubagentStop: `sh ~/.claude/scripts/tools/hook-python ~/.claude/scripts/gates/staged_claim_gate.py`. The work security hook refuses a settings edit from a session, so the user adds the two entries by hand.
- Closes the queue item a-hand-back-that-says-files-are-staged-never.

## Evidence

- One main session told the user files were staged while the index did not hold them. No script or skill text makes the claim, so a rule edit could not reach it.
- The new tests fail before the script exists.

## Result

- The 12 staged-claim tests pass, ruff is clean, and the duplicate-code check passes.

## Watch

—

## Back-out

Remove the two settings entries and delete the script and its test.
