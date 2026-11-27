---
type: "Change"
change_type: "added"
title: "a zsh test pins the CLAUDECODE guard on the ls alias"
description: "A test runs a real interactive zsh over the zshrc and checks that ls is the system command under CLAUDECODE and an alias otherwise."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T12:49:56-06:00"}
seq: 6
kind: "fix"
components: ["script/zshrc"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_zshrc.py::ZshrcLsAliasTest::test_claude_code_shell_resolves_guarded_names_to_the_command"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`tests/scripts/test_zshrc.py` starts `zsh -i` with a scratch home and a stub `keychain`, loads the stowed `.zshrc`, and
reads `whence -w ls` and `whence -w cat`. With `CLAUDECODE=1` it must print `ls: command`; without it, `ls: alias`.

## Evidence

Judgment: the test runs at the shell boundary, with no mocks of the zshrc.

## Result

A change that aliases `ls` inside Claude Code's Bash tool, where GNU flags must reach the real `ls`, now fails a test.

## Watch

None: `type ls` in a Claude Code Bash call shows the path to the system `ls`.

## Back-out

Delete the test file: the guard stays, unpinned.
