---
type: "Change"
title: "review-commit-gate lets a probe that mentions the commit words pass"
description: "In a dirty session the gate denies a command when a parsed git call commits, in the command or in a `$( )` or backtick span, when a command it cannot read holds git then commit, or, failing closed, when any simple command is not a safe probe and the text holds the commit words. An echo, printf, grep, rg, cat, head, tail, wc or read-only git probe that prints or searches the words passes. A heredoc whose body holds the words is still denied unless its tag is a probe program's name."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T14:00:00-05:00"}
seq: 222
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_a_probe_that_only_prints_or_searches_the_commit_words_passes_while_dirty"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/scripts/review/review_commit_gate.py`: `reads_as_commit` no longer matches `git commit` in every command's text. A simple command counts when it runs git with any global options and then `commit`, in the command or in a `$( )` or backtick span.
- Fail closed: `is_safe_probe` passes a simple command whose first word, as written, is in `PROBE_PROGRAMS` (echo, printf, grep, rg with no `--pre` or `--hostname-bin` word, cat, head, tail, wc), or is git with a read-only subcommand and no `-c` or `--config-env`. When any simple command is not a safe probe, the text patterns (`COMMIT`, `GIT_THEN_COMMIT`) run on the whole reading, as written, with quoted-string joins removed, and with quotes and backslashes removed. So the spellings the text patterns read (`\sh -c`, `env -S`, `awk` `system()`, the split-words probe, `git 'commit'`) stay denied, with no list of code runners.
- A `$( )` or backtick span is judged whether or not every simple command is a safe probe.
- A command shlex cannot read counts on `UNREADABLE_GIT_THEN_COMMIT`, `COMMIT` and `GIT_THEN_COMMIT`, each on the same three texts, so the fail-closed rule holds for readable and unreadable commands.
- Limits: the lexer splits a heredoc at each newline, so each body line and the closing tag line read as simple commands. The tag line is a safe probe only when its word is a probe program, so a heredoc tagged with such a name (`cat`, `echo`, `rg`...) whose body holds the words passes. With any other tag, the tag line is not a probe and the words are denied.
- Limits: a read-only git probe trusts the repo's own config (`core.pager`, `diff.external`, `core.fsmonitor`) and the git environment an earlier command or an assignment sets (`GIT_EXTERNAL_DIFF`, `GIT_PAGER`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_PARAMETERS`); only `-c` and `--config-env` are refused. A value built from split words, as in the next bullet, passes this way too.
- Limits: a commit built from text the gate never sees whole (`echo commit | xargs git`, `printf 'git%s' ' commit' | sh`) passes, as on the base gate.
- Limits: a script file run by its path (`./probe.sh`) is not read. A push is not judged by this gate.
- Closes the queue item review-commit-gate-denies-any-command-whose-text.

## Evidence

- In two review rounds, the gate denied reviewer probes that only printed or tested commit-shaped text. A reviewer with no Write tool had no approved path and reworded the probe.

## Result

- On the base gate, nine echo, printf, grep, rg, cat, head, tail, wc and read-only git probes are denied. On the new gate they pass. A new test checks that a commit inside `$( )`, backticks, `bash -c`, `\sh -c`, `env -S`, `awk` `system()`, `rg --pre`, a `git -c core.pager` or a pipe into `sh` is still denied. A heredoc tagged `EOF` whose body holds the words is denied. All 110 commit-gate tests pass.

## Watch

—

## Back-out

Revert the commit. A probe that mentions the commit words is denied again in a dirty session.
