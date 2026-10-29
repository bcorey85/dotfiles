---
type: "Change"
change_type: "fixed"
title: "verify-prep hands plan-verifier its run rules"
description: "At branch end, plan-verifier ran every test file it could find, including one that snapshots the real ~/.claude. It wrote log files into a sibling checkout and deleted them, and it left a background test run going. verify-prep's payload is the only dispatch prompt plan-verifier gets, and it carried no run rules. The payload now ends with four: run the plan's commands as written and beyond them only a covering test's file, never run a self-chosen test that touches files outside the checkout (user config or sibling repos), run in the foreground and leave no process, and delete, move, kill or create nothing but a Manual Verification checkbox line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T11:04:42-05:00"}
seq: 187
kind: "fix"
components: ["script/verify-prep"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_the_verifier_payload_carries_the_run_rules"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `verify-prep`: a new `VERIFIER_RUN_RULES` tuple. The plan-verifier payload ends with a `run rules:` block that lists them:
  - Run each Automated Verification command the plan lists, as written. Beyond those, run only the file of a covering test the plan's commands do not run. No other test and no suite sweep of its own.
  - Outside the plan's own commands, never run a test or command that snapshots, edits, creates or deletes files outside this checkout (~/.claude, ~/.config, sibling repos); a tool reading its own config (git, npm) is fine. A covering test file this forbids is not run: its criterion can still be covered by reading the test, with a note that it was not run. A Manual Verification item whose command does this is human-only.
  - Run every command in the foreground. Start no background run and leave no process running. A Manual Verification item that needs a process left running is human-only.
  - Delete, move or kill nothing. Create no file yourself: the only write is a Manual Verification checkbox line.
- Closes the queue items plan-verifier-runs-live-data-tests-and-deletes and plan-verifier-runs-live-home-tests-deletes-files.

## Evidence

- Two slice reports of one branch-end run: plan-verifier ran a test that snapshots the real `~/.claude`, wrote and then deleted log files in a sibling repo, and left a background test run whose kill was denied. The caller's rules never reached it, because verify-prep's payload is the only dispatch prompt and named none.
- The new test fails before the change: the payload had no run rules.

## Result

- The 118 verify-branch script tests pass, ruff is clean, and the duplicate-code check passes.

## Watch

—

## Back-out

Revert the commit. plan-verifier then runs with no run rules in its prompt again.
