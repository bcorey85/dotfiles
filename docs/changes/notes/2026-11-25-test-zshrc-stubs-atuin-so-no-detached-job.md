---
type: "Change"
change_type: "fixed"
title: "test_zshrc stubs atuin so no detached job recreates the temp home"
description: "The zshrc test puts a no-op atuin on PATH, so atuin's init starts no detached job that recreates the temp home while cleanup removes it, and the full suite stops failing this file under load."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:09:18-06:00"}
seq: 3
kind: "fix"
components: ["method/test-suite"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_zshrc.py::ZshrcLsAliasTest::test_interactive_shell_without_claudecode_aliases_guarded_names"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`tests/scripts/test_zshrc.py` setUp writes an `atuin` stub (exit 0, no output) beside the `keychain` stub. The zshrc's `eval "$(atuin init zsh)"` then evals nothing. No assertion changed.

## Evidence

atuin's zsh init runs `(atuin __internal prepare-search-index >/dev/null 2>&1 &)`, a detached job that outlives the test's zsh. It creates `$HOME/.atuin`, which recreates the temp home after `TemporaryDirectory` cleanup has listed the root, so `rmtree` fails with Errno 39 on the root. The full suite hit it twice in one day.

## Result

A replay of the test's setup that removes the temp root right after zsh exits: with the real atuin, the home came back in 60 of 60 runs and `rmtree` failed in 1; with the stub, 0 of 60 and 0 failures. The file then passed 20 runs in a row under the memory cap while a full `bash tests/run.sh` ran beside it (6664 tests, 0 failed).

## Watch

None. Merges stop rerunning this file by hand.

## Back-out

Drop `"atuin"` from the stub loop in `test_zshrc.py` setUp.
