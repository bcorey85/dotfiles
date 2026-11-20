---
type: "Change"
change_type: "added"
title: "The git discipline gate denies destructive git in a main checkout, read past git's global options"
description: "`git_discipline_gate.py` rule 7 denies a forced push, a push naming main or master, `reset --hard`, `clean -f`, a whole-tree discard and `--no-verify` in a main checkout, read past `-C`, `-c`, `--no-pager`, `--git-dir`, `--work-tree` and `-q`; aliases are not read. Rule 7 passes a linked worktree; `bash-safety-gate.sh` still denies the plain spellings everywhere."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T23:54:09-06:00"}
seq: 1
kind: "fix"
components: ["script/git-discipline-gate"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::DestructiveGitCallsTest::test_each_destructive_call_is_denied_in_a_main_checkout_in_every_spelling"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `lib/git_destructive_calls.py`: `destructive_reason(call)` names the destructive rule a parsed git call breaks, or None. `--no-verify` is read on `commit`, `push` and `merge` (`commit -n` too, not `merge -n`); the value word of a push option (`-o`, `--push-option`, `--repo`, `--receive-pack`, `--exec`) is no refspec.
- `lib/git_calls.py`: reads `--git-dir` and `--work-tree` to find the call's repo; an unquoted `GIT_DIR=`, `GIT_WORK_TREE=`, `GIT_COMMON_DIR=`, `CDPATH=`, `HOME=` or `GIT_CONFIG_*=` assignment (quoted text that names one is no assignment; `env "GIT_DIR=x" git ...` is), a `cd` the gate does not follow (including one that runs only on a condition) and a `pushd` or `popd` leave the call unplaced (read as a main checkout); `is_linked_worktree(call)` runs one `git -C <dir> [--git-dir ...] rev-parse --absolute-git-dir --git-common-dir` and calls the repo linked when the two differ. With `--git-dir` and no `--work-tree` the call's directory must also be in a linked worktree. A repo the gate cannot find, or a failed `rev-parse`, reads as a main checkout. A call cut from code-runner or launcher text is unplaced. `env -C<dir>` and `sudo -D` count as directory moves.
- `lib/git_destructive_calls.py`: cluster letters are read before a value letter (`restore -sStable .`, `clean -fdx -enode_modules`).
- New `lib/git_subcommand_options.py`: the protected branch names, git's false config values, and how `checkout`, `switch` and `restore` options take values (`restore_stages`, `restore_restores_worktree`, `discards_on_switch`, `is_orphan_option`, `takes_separate_value`) move here from `lib/git_destructive_calls.py`; the git discipline gate and `git_destructive_calls.py` import them.
- `gates/git_discipline_gate.py`: rule 7 applies them to every git call in the command, later statements and substitutions included, placed from the payload's `cwd`. Rule 7 passes a linked worktree; `bash-safety-gate.sh` still denies the plain spellings everywhere. The deny text tells the agent to ask the user to run the call.

## Evidence

User ruling of 2026-11-15 on the queue item: deny in a main checkout, allow in a linked worktree, no settings.json edit. The bash safety gate matched only the plain `git push --force` spellings, so `git -C <dir> …`, `-c k=v` and `-q` before the flag ran.

## Result

`DestructiveGitCallsTest` covers 67 destructive calls across the six rules (forced push, push naming main or master, `reset --hard`, `clean -f`, whole-tree discard, `--no-verify`) and 31 harmless calls, in the plain, `-C`, `-c`, `--no-pager`, `--git-dir` and `--work-tree` spellings (`-q` forms are their own cases), denied in a main checkout and passed in a linked worktree; `git -C <repo> push -u origin HEAD` and `git -C <dir> status` pass.

Median time on matched calls, 15 runs of 4 calls: branch 34.0 ms, master 34.0 ms; bare Python start 7.7 ms.

## Watch

None: a deny on a destructive call is the whole effect.

## Back-out

Revert the commit.
