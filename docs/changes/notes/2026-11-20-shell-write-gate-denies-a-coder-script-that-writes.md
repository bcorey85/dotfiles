---
type: "Change"
change_type: "fixed"
title: "Shell write gate denies a coder script that writes computed paths outside temp"
description: "A coder's interpreter step whose file write target comes from a glob, a directory listing, argv or a loop over one is denied unless the path is proven under a temp dir."
generated: {"by": "claude-sonnet-5-5/coder", "at": "2026-11-20T19:33:15-06:00"}
seq: 1
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["queue item coder-rename-passes-run-regex-scripts-that-can: a coder rename script looped over repo files with re.sub and wrote each back, with no backup"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_coder_script_writing_files_found_by_a_glob_is_denied_naming_the_rule_and_edit_or_lsp"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/interpreter_writes.py` gains `computed_write_target`; `gates/shell_write_gate.py` applies it to coder requests only and denies with the new `coder_computed_write` tag. The deny names the rule and points to the LSP rename or the Edit tool. Temp proof is per write target, not per argument: a mkdtemp, gettempdir or TemporaryDirectory base, or a literal temp path, anywhere in the target's trace counts as proof, even when the write lands outside that folder. Known gap: a script that makes a mkdtemp folder and then moves or writes out of it (a loop that moves listed repo files into the folder) is read as proven and is allowed (`names_temp_base` finds the mkdtemp base in the target's trace, so `computed_write_source` moves on to the next write); a removed tracked file shows in git status. An argv script stays denied when any argument is not a temp path, read-only arguments included. Main-session verdicts are unchanged.

Accepted limits: a write call inside a string literal of a generator script counts as a write of that script, and `.replace(` moves are unchecked.

A `|a|` in perl or node is a regex alternation and binds no name; only ruby reads it as block parameters.

## Evidence

The incident script shape (glob loop, `pathlib.Path(f).write_text(re.sub(...))`) was allowed before and is denied now; the gate tests pin it, along with each listing call and the temp-base and argv cases.

## Result

Replay of 12002 real Bash commands from local transcripts (each through 8 gates as the main session and 3 as a coder, 132022 results) over the final tree against the earlier replay of the same corpus. Differences that are only the random temp folder name inside the deny text are no change. 16 differ after that, all in `shell_write_gate.py`, and no other gate changed. 2 of the 16 change only the deny text (a restore hint added), not the verdict. The other 14 changed results are 12 as a coder (4 of them deny to deny with a new tag) and 2 as the main session; the two main-session ones come from the backslash-newline join (see the continuation note). Each was read:

- 5 coder allow to deny `coder_computed_write`, all scripts that write a path taken from argv or a listing with no temp proof, each read as a true write of computed paths: an eval script that globs a repo folder and rewrites each file (`add_suffix.py`, listing); `full_check.py` run twice with a `--log` path and a repo path (one deny names the argv source, one the listing source); a `python3 -` stdin script that opens `sys.argv[1]` for writing, given a `$S/...` path the gate cannot resolve to a temp folder; `start_review.py` launched with plan and handoff paths. The argv ones write a state or log file named by an argument and are denied because an argument is not a temp path (ruled, argv denial kept); they are the cases to watch.
- 4 coder deny to deny with a new tag, no verdict change: two commands that `cd` to a folder and start `python3 run.py` (before `coder_rel_target_cd`, now `coder_computed_write`: a relative script is read in the folder the step runs in, so its argv write is found), an in-place `sed -i` plus argv script (before `inplace_edit`), and a heredoc target after a `cd` to a scratchpad (before `rel_target_unread_cd`, now `coder_rel_target_cd`).
- 2 coder deny to allow: a scratchpad heredoc script whose `$S` folder the gate could not resolve until the backslash-newline join (a write under a temp folder, a correct allow), and a scratch repo whose tracked file no longer exists on this disk (a change in the disk, not in the code).
- 1 coder allow to deny `inplace_edit` and the same command as the main session: five `sed -i` edits of rig scripts in a real folder after `&& \` and a newline; the continuation was not joined before, so the step was read as one word. A correct deny: a `sed -i` of a real file.
- 1 main-session deny to allow, a `printf ... > fill_queue.py` write into a session scratchpad after a `cd` to it, with backslash-newline joined lines: the target is a temp path, so the allow is correct (the earlier deny read the continuation lines as an unreadable `cd` folder). This is a deny to allow for the main session, the one main-session change that is not a deny of a tracked or real target.
## Watch

Coder runs that script a legitimate loop over repo files and are denied; each one is the case to review. A script that lists a temp folder and writes the listed names into the working folder is allowed, because the temp base in the trace counts as proof.

## Back-out

Remove `check_computed_writes` from `check_script_writes` in `gates/shell_write_gate.py`.
