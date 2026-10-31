---
type: "Change"
change_type: "changed"
title: "A shell write denied after a cd says to use an absolute path"
description: "When shell-write-gate denies a redirect or tee to a relative git-tracked path in a command that runs a cd before it, the deny message says the gate resolves a relative path against the session cwd, so use an absolute path; the gate still resolves the target against the session cwd and no deny becomes an allow."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T20:00:54-05:00"}
seq: 293
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_deny_after_a_directory_change_says_a_relative_path_follows_the_session_cwd"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The git-tracked deny for a redirect or `tee` to a relative path, in a command that runs a `cd`, `pushd` or `popd`
  before the write, adds one line: this gate resolves a relative path against the session cwd, not the `cd` target, so
  use an absolute path for the file you mean. Other denies are unchanged.
- The gate does not follow the `cd`. What it denies and allows is unchanged.

## Evidence

- A subagent appended to a scratch file after `cd <scratch dir>`. The gate resolved the name against the repo, saw a
  tracked file of the same name, and denied it. The message did not say why, so the agent spent a round trip finding
  out.

## Result

- The named test runs `cd <scratch dir> && echo y >> tracked.txt` from a repo that tracks `tracked.txt`, plus `pushd`
  and subshell forms. Each is still denied, and the message names the absolute-path fix. A deny with no `cd` before the
  write gets no hint, and neither does an absolute target after a `cd`.

## Watch

None: no intake number reads the deny message's text.

## Back-out

Revert the commit.
