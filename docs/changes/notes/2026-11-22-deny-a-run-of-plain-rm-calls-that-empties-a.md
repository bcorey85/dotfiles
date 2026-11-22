---
type: "Change"
change_type: "added"
title: "Deny a run of plain rm calls that empties a directory like the recursive form"
description: "git-discipline-gate denies a Bash command whose plain rm targets cover every entry of an existing directory outside a temp or build folder, naming the directory and the rm -r form bash-safety-gate denies; the check reads the file system, so the last per-file delete of a split run is caught too. The hook's median time on a matched call is 37 ms against an 8 ms bare Python start."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T12:19:03-06:00"}
seq: 4
kind: "fix"
components: ["script/git-discipline-gate", "script/directory-emptying-deletes", "script/shell-steps", "script/shell-command"]
evidence: ["queue item coder-bypasses-a-blocked-recursive-delete-with-per: bash-safety-gate denied rm -r on a directory and the coder deleted its files one by one, then rmdir, every call passing"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::DirectoryEmptyingGateTest::test_the_last_delete_after_an_earlier_call_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `lib/directory_emptying_deletes.py`, the owner of which directories a command's plain `rm` calls would empty: `emptied_directories(command, directory)`. Each simple command is placed through `lib/shell_steps.py` `placed_commands` (a `cd` moves later calls; a `cd` to an unread folder leaves them unplaced), its raw words come from `lib/shell_command.py` `parse_raw_simple_commands`, globs expand in the call's folder, and a directory is reported when it exists and every `os.listdir` entry is a target. Recursive `rm` is left to bash-safety-gate. Not reported: a folder under a temp root, a folder whose path holds a name in `SAFE_FOLDER_NAMES` (the same allowances as bash-safety-gate's `rm_recursive_force` safe list), a target with a mark the gate does not read (`$`, backtick, `~user`, braces), and a folder that cannot be listed (that part fails open, with a comment).
- `gates/git_discipline_gate.py` rule 9 raises `DenyError` opening `[git-discipline-gate] rm of every entry in <dir> empties it:` and says that a blocked delete is never split or disguised: leave the files and report a stop so the user runs `rm -r <dir>`.
- Known limits, in the module docstring, no code: brace targets (`rm d/{a,b}`), a `cd` inside a subshell, and a folder named as a target.
- Owners line in `claude/.claude/scripts/CLAUDE.md`; the module in both lib lists of `docs/toolkit-script-rules.md`.

## Evidence

Queue item coder-bypasses-a-blocked-recursive-delete-with-per: bash-safety-gate denied `rm -r <dir>`, and the coder deleted the directory's files one by one, then `rmdir`, each call passing.

Hook time, 30 runs each, payload cwd a fixture repo outside the temp roots: bare `python3 -c pass` 8 ms median; the gate on a matched `rm d/a d/b` 37 ms median; the gate on an unmatched `git status` 37 ms median. The rule adds no measurable time on an unmatched call.

## Result

A per-file delete that empties a directory is denied with the same stop as the recursive form. A delete that leaves an entry behind passes. The cross-call shape is caught on the last call: after `rm d/a` has run, `rm d/b` on the one-file directory is denied.

## Watch

No registered watch. The next hook census counts git-discipline-gate denials whose reason opens with `rm of every entry in`, and how many are followed by a reported stop rather than a reworded delete.

## Back-out

Revert the commit. `settings.json` is unchanged, so no hook entry moves.
