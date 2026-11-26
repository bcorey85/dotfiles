---
type: "Change"
change_type: "fixed"
title: "Foreground-suite deny names a cap command only where the host runs it"
description: "On a host with no systemd scope, such as macOS, the foreground full-suite deny names run_in_background alone, so the approved path it names can run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T18:10:00-06:00"}
seq: 8
kind: "fix"
components: ["script/memory-cap-scope", "script/inline-interpreter-hint"]
evidence: ["queue: test-run-hook-tells-macos-sessions-to-use-systemd"]
watches: []
test: "tests/scripts/test_memory_cap_scope.py::BackgroundDenyTextTest::test_the_hook_names_run_in_background_alone_on_a_host_with_no_scope"
asked: ""
proof: []
unmeasured: "No logged rate; each hit on darwin named a command that cannot run there."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `lib/memory_cap_scope.py`: `background_deny_text()` replaces `BACKGROUND_DENY_TEXT`. It names the capped `systemd-run` command only where `cap_available()`; elsewhere it names `run_in_background` alone.
- `gates/inline_interpreter_hint.py` calls it.

## Evidence

The hook told macOS sessions to rerun the suite inside `systemd-run`, which darwin does not have.

## Result

The new tests fail before the change and pass after. Linux hosts with a user systemd keep the capped text.

## Watch

None.

## Back-out

Revert the commit.
