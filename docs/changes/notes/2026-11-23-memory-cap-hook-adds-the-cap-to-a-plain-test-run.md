---
type: "Change"
change_type: "changed"
title: "Memory-cap hook adds the cap to a plain test run in place of denying it"
description: "A single plain test command that lacks the memory cap now runs capped on the first call, with the cap added by the hook, in place of a denied call and a resend. A test runner named by a path (`./pytest`, `.venv/bin/pytest`) is now denied until it carries the cap."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-23T02:22:41-06:00"}
seq: 3
kind: "fix"
components: ["script/inline-interpreter-hint", "script/check-scope", "script/memory-cap-scope"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_memory_cap_scope.py::HookTest::test_a_plain_test_step_gets_the_prefix_added"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `gates/inline_interpreter_hint.py` returns `updatedInput` with no `permissionDecision` when an uncapped test run is one plain step: the command with the memory-cap prefix in front and every other tool input key kept. The rewritten command then goes through the normal permission rules and is not auto-approved (code.claude.com/docs/en/hooks, the `updatedInput` row). A usage-flag run (`pytest --help`) and a machine with no cap pass with no output. It denies in every other case; see the path-named runner below for a new deny.
- `lib/memory_cap_scope.py` owns the test for a plain step and builds the capped command. A plain step has no chain, pipe, background `&`, group, substitution, redirect, heredoc or leading assignment, and its program word holds no `/`, except the repo's own `tests/run.sh` (`tests/run.sh` or `./tests/run.sh`, alone or after a shell); a run script at any other path is denied.
- `lib/check_scope.py` `program_runs_tests` says whether the program word itself is a test runner, so a test word in the arguments (`rm -rf x pytest`, `sudo pytest`) is never rewritten.
- A foreground full suite in a main session is still denied with the text that says to run it in the background. A path-named runner such as `./pytest` or `.venv/bin/pytest` is now denied with the cap text (it was not denied before); it is never rewritten. Test: `tests/scripts/test_memory_cap_scope.py::HookTest::test_a_command_that_is_not_one_plain_step_is_still_denied`.

## Evidence

- judgment: in one session the hook denied three test runs for the missing prefix, and one denied call was resent unchanged and denied again. The fix each time was the same mechanical prefix.

## Result

- The named test fails on the tree before the change and passes after.
- Hook median wall time over 25 runs, master then this branch, same machine and load: a plain test step 56 → 57 ms, a chained test step (deny) 56 → 52 ms, an already capped step 50 → 57 ms. A bare `python3 -c pass` start took 11-12 ms in the same runs. An earlier quieter run gave 35/35/31 ms before and 39/38/36 ms after, with an 8 ms bare start.

## Watch

After landing, run one plain uncapped test step in a session and confirm it starts a systemd scope (`systemctl --user list-units --type=scope` shows a `run-*.scope` while it runs). No scope means Claude Code ignored `updatedInput` and the run went uncapped.

In a session type that refuses a hook-changed call, Claude Code answers with one of two messages: "A settings hook changed this tool call's input. That is allowed only for calls that run in the same environment as the hook, and this one does not, so the call was not made." or "A hook from the user's own Claude Code files tried to change this tool call's input. In this session such hooks may block or ask about a call but not change it, so the call was not made." Seeing `changed this tool call's input` or `so the call was not made` means the rewrite must be reverted to the deny (`DENY_TEXT`) for that session type.

## Back-out

Revert the commit. The hook then denies a plain uncapped test run again, and a path-named runner (`./pytest`) passes with no output, as before.
