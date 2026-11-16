---
type: "Change"
change_type: "fixed"
title: "shell write gate proves a temp target that holds a variable, and tags every deny"
description: "A coder may now redirect into a temp file whose name holds a variable the gate can prove, such as a `for` name over literal words. Every deny carries a fixed tag, so each deny branch can be counted."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T17:46:03-06:00"}
seq: 9
kind: "fix"
components: ["script/shell-write-gate", "script/shell-command", "agent/coder"]
evidence: ["shell-write-gate-coder-blocks-rose-ninefold-after"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_a_coder_may_redirect_through_a_for_variable_over_literal_words"
asked: ""
proof: []
unmeasured: ""
---

## Change

**Variable targets.** The gate denied a coder every redirect or `tee` target with a `$` in it. It now allows one
when it proves every value the target can take, and every value resolves under a temp dir (symlinks and `..`
followed). A value is proven in two ways only:

- one bare `NAME=value` or `export NAME=value` step before the use, joined by `;`, `&&` or a newline, with the name
  assigned nowhere else in the command;
- a `for NAME in word word` loop over literal words, used inside its own body. Nested loops multiply, up to 64
  combinations.

Everything else keeps the deny, and the gate fails closed. Unproven: a name with no assignment in the command; a
second assignment (`S=`, `S+=` or a zsh `S[1,2]=`); a name inside a subscript or nameref value (`declare -n R='S[0]'`,
`a[S=1]=`), and any subscript that is no integer literal, inside quotes too (a quoted `name[` in any argument keeps
the deny: `S=/tmp/x; grep "foo[0-9]" f > $S/a` is a `coder_unresolved_var` deny; `$a[S-=2]` and `$[E]` too); a zsh
`set -A` array name (`set -A S`, `set -eA S`); a `[[ A -eq B ]]` test (any of `-eq`, `-ne`, `-lt`, `-le`, `-gt`, `-ge`)
unless both operands are numeric literals, because it reads a variable as arithmetic; a name that stands anywhere in the command as a bare word
(`read S`, `unset S`, `declare S`, `integer S`, `vared S`, `print -v S`, `printf -v S`; a backslash before the name or
a `$` after it still counts); a name that the quote-removed words of a step show as a word or an assignment
(`unset \S`, `declare S\=x`), or as `NAME=` anywhere inside a word (`E=S\=7`, which `[[ E -eq 7 ]]` reads as
arithmetic); a name that ends an option cluster of a name-setting builtin (`printf -vS`, `read -raS`, `print -vS`);
a name-setting builtin (`declare`, `typeset`, `local`, `readonly`, `export`, `read`, `printf`, `print`, `unset`,
`getopts`, `mapfile`, `readarray`, `vared`, `wait`, `zparseopts`, `integer`, `float`) whose option word, or whose name
operand (the word after `-v` for `printf` and `print`; every operand up to its `=` for the others), holds `$`, a
backtick or a backslash, because it can compute the name (`printf -v "${N/T/S}"`). The whole step is scanned, so a
word after a redirect counts, and a format string or another program's text does not (`printf '%s\n' "$t"`, `awk
'{print $1}'`); a value that holds `=` (zsh expands `=cmd`); a name written as a named descriptor (`{S}>file`); a name the shell sets
or refuses to let a command set (`REPLY`, `reply`, `OPTARG`, `OPTIND`, `MAPFILE`, `PWD`, `OLDPWD`, `RANDOM`,
`SECONDS`, `LINENO`, `UID`, `EUID`, `PPID`, `BASHPID`, `SRANDOM`, `EPOCHSECONDS`, `EPOCHREALTIME`, `HISTCMD`,
`BASH_COMMAND`, `GROUPS`, `SHLVL`, `_`, `MATCH`, `MBEGIN`, `MEND`, `match`, `mbegin`, `mend`, `BASH_REMATCH`,
`DIRSTACK`, `USERNAME`, `FUNCNAME`, `BASH_SUBSHELL`, `BASH_LINENO`, `BASH_SOURCE`, `BASH_ARGC`, `BASH_ARGV`,
`COPROC`, `pipestatus`, `SHELLOPTS`, `BASHOPTS`, `BASH_VERSINFO`, `BASH_MONOSECONDS`, and both names of each zsh tied
pair: `PATH`/`path`, `CDPATH`/`cdpath`, `FPATH`/`fpath`, `MANPATH`/`manpath`, `MAILPATH`/`mailpath`,
`MODULE_PATH`/`module_path`, `FIGNORE`/`fignore`, `PSVAR`/`psvar`, `WATCH`/`watch`); a name looped over by a second `for`, also one that already ended; any `IFS` in the command; an
assignment in a subshell, a group, a function, an `if`, a `while`, `until` or `for` loop, a pipe, a background step, or after `||`; a value or loop word with a `..` path part, or any character beside letters, digits and `_@%+:,./-`; a step with a `$` in single quotes or after a backslash (`sed '$d'`); a `for` header that is no `for NAME in`, and a `do`, `done` or `fi` with no matching opener; a prefix assignment
on a command; `eval`, `source`, `trap`, `.` (also after `if`, `then`, `command`, `builtin`, `nocorrect`, `noglob` or a lone `-`), `let`, `select`, `case`, `alias`, `setopt`, `unsetopt`, `emulate`, a function definition, `export -n` or `((` anywhere (`set -o pipefail` keeps the proof); a
loop over a glob, a variable or a command substitution; `$(...)`, backticks or `$((...))`; any `${...}` that is not
exactly `${NAME}`; a target that holds anything beside the references and safe characters (a zsh subscript
`$S[1]`, modifier `$S:h`, glob qualifier `$S/a(:h)`, numeric range `$S/a<->`, `#`, `^`, a glob, a brace list, `~`, a
backslash) or starts with `=`; a step with a `(` or `<` against the word before it, anywhere in the command (a
glob qualifier can run code); an unbraced `$NAME:` modifier anywhere; a step with any backtick, quoted or
not (a backtick span the reader does not follow); a `}` at the end of a step while a `( ... )` subshell is open (a
`}` closes only a `{` group); a heredoc fed to a shell (its body sees no variable of the parent); a
value with a space. Only an unquoted `(` or `)` opens or closes a group, so `echo ")"` inside a subshell stays a
subshell. A loop
word that is a builtin name (`for t in read write`) is no reason to deny.

`$TMPDIR` and `$HOME` in a coder's target are no longer read from the hook's environment when the command assigns
them, names them as a bare word, or loops over them in a `for` header (even when the rest of the command is
unreadable): `TMPDIR=/etc; echo x > $TMPDIR/a` is now denied, also inside a double-quoted
`$(...)`. A target inside a `$(...)` span proves no variable. An unproven variable target after a `cd` is a
`coder_unresolved_var` deny, not a relative-target deny.

**Tags.** Every deny reads `[shell-write-gate] [<tag>] <message>`. The tags are `script_write_rel_cd`,
`script_write`, `inplace_edit`, `tracked_target`, `rel_target_unread_cd`, `coder_rel_target_cd`,
`coder_unresolved_var`, `coder_var_outside_temp`, `coder_new_file`, `input_parse_fail` and `internal_error`.
`coder_var_outside_temp` is a proven value that resolves outside every temp dir, symlinks followed before any `..`.
`lib/shell_write_denial.py` owns the list and is the only builder of the text.

**In-place message.** The deny for `sed -i`, `perl -pi` and `awk -i inplace` names the file operands. It named the
last word of the step, which was often a word of the sed script. When the gate finds no operand (a command cut off
inside a quote, for one), it says so and quotes nothing. An in-place edit is allowed only when every file operand is
a scratch file. A file list the gate cannot see (`find -exec sed -i ... {}`, an editor behind `xargs`, `parallel` or `fd -x`/`-X`)
counts as an operand that is no scratch file, so it is denied, also when the command runs in a temp dir. An `-x` or
`-X` flag counts only for `fd` and `fdfind`. A quoted or escaped word that looks like a redirect (`'>&'`, `\>`) is a
file word and hides no operand after it. The old check read only the last word, so `sed -i s/a/b/ repo-file scratch-file` passed. The BSD form
`sed -i '' 's/a/b/' scratch-file` stays allowed: the empty word after a bare `-i` is its backup suffix, no operand.

**Split.** The gate was 1,180 lines and is 477. The interpreter-write trace moved, unchanged, to
`lib/interpreter_writes.py`. New modules: `lib/shell_variables.py`, `lib/inplace_edit.py`,
`lib/shell_write_denial.py`, `lib/shell_write_paths.py`. `lib/shell_command.py` gained `closed_segment_words` and
`words_by_blank` (the blank split that `segment_words` falls back to, used by `inplace_edit` and
`interpreter_writes`). It also gained `REDIRECT_WORD`, `is_redirect_word` and `words_without_redirections` (the
words of a step with each unquoted redirect and its target left out), and new `nocorrect`, `noglob` and `-`
entries in `WRAPPER_VALUE_OPTIONS` that change `command_after_wrappers` for every caller.
`docs/toolkit-script-rules.md` lists the five new modules.

## Evidence

Coder blocks by this gate per coder run rose from 0.12 to 1.07 over three weeks at work. In the local transcripts,
139 coder denies came from the `$` check, which arrived with commit `92ef3813` on 2026-10-27. The common shapes are
`for t in a b c; do cargo test --test $t > /tmp/t_$t.log; done` and `S=<scratchpad>; cargo test > $S/a.log`.

## Result

The still-denied reasons name `${f%%:*}` as a target shape: the reader rejects it anywhere in the command. A quoted
`name[` whose subscript is no integer literal (`grep -E "v[0-9]"`) also keeps the deny, even in a regex or an awk
script.

All 761 local deny rows were replayed through the old and the new gate, once as a coder and once as the main
session. As a coder, 113 rows changed from deny to allow: 104 of the 139 `$` rows, and 9 rows the old gate called a
relative target after a `cd` because it read `$S/x` as relative (a tenth such row is cut off inside a quote and stays
denied). No row changed from allow to deny. As the main
session, all 761 verdicts are the same. Of the 139 `$` rows, 19 are still denied as unproven: they use a counter
(`$((i+1))`), a loop over `$(seq ...)`, a `${f%%:*}` form, a name assigned twice, or a `$` in single quotes
(`sed '$d'`), or the saved row is cut off at 400 characters inside a loop. One cut-off row ends in `--profile t`, a
bare word equal to its loop name; the full command says `--profile test` and passes.

A bare word equal to a variable's name anywhere in the command makes that name unproven, so
`for t in a b; do ... > /tmp/x_$t.log; done; rg -n t file` is denied. No full row in the replay has that shape.

A second replay took 7,500 distinct Bash commands from the local transcripts, newest first (6,000 with a redirect,
`tee`, `sed`, `perl`, `awk`, a loop or a `$`, and 1,500 plain ones), and ran each through both gates in the folder
it ran in. It ran on the current tree, after the stricter reader. As a coder, 76 changed from deny to allow, each one
a write under `/tmp/` through a variable assigned once or a `for` name over literal words; none changed from allow
to deny; 7,252 stayed allowed and 172 stayed denied. As the main session, one verdict changed, from allow to deny
(7,458 stayed allowed, 41 stayed denied): `printf '%s' 'ls | parallel sed -i s/a/b/' > cases5.txt`, a probe command
of this change's own review. Both gates read the quoted text as an in-place edit; the new one denies it because the
file list behind `parallel` is unseen. The new gate gave no error. Over the 30,000 hook runs the median time is
35.4 ms (36.3 ms before) and the 95th percentile 40.1 ms (40.9 ms before), with four runs at a time.

A probe of 24 hostile commands (21 that must be denied, 3 that must pass) gives 0 wrong verdicts.

Of the 379 in-place rows, 330 messages name real file operands and 29 say that no operand was found. The rest are
allowed in the replay because their files do not exist there, or carry another tag.

Tests: 155 in `tests/scripts/test_shell_write_gate.py`, 46 in the new `tests/scripts/test_shell_variables.py` and 11
in the new `tests/scripts/test_inplace_edit.py`. A
walk over every deny branch fails on a deny with no tag or a tag off the list.

The hook's median time on a matching call is 37.3 ms for the loop form (38.5 ms before) and 36.1 ms for the
assigned form (37.5 ms before), beside 7.8 ms for a bare Python start.

## Watch

None here. The intake counts shell-write-gate blocks by tag, so `coder_unresolved_var` per coder run is the number
to read after this ships.

## Back-out

Revert the commit. Coders are then denied every variable target again, and denies lose their tags, so the intake
counts them as untagged.
