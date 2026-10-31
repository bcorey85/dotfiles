---
type: "Change"
change_type: "fixed"
title: "shell-write-gate lets a script read a tracked file passed as an argument"
description: "An untracked script that writes only files it names itself can now take a tracked file as an argument; a script with a write target that may come from argv is still denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T14:05:09-05:00"}
seq: 386
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_untracked_script_that_reads_a_tracked_argument_and_writes_its_own_file_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The interpreter-write check counts a tracked argument as written unless the trace finds that no write target comes
  from argv. Each write call (`open` in a write mode, `write_text`, `writeFile`, copies, moves, renames, deletes and
  truncates in python and node, `unlink`, `rename` and `open` for writing in perl, `File` and `FileUtils` calls in
  ruby, `fileinput` in place) has its target read: the receiver of a method; the last argument of a `shutil` copy, a
  ruby `FileUtils.cp` and a perl `open`; the second argument of a node `.copyFile` or `.copyFileSync`, since a
  callback or mode may follow it; the first argument of a call that writes content
  (`writeFile`, `File.write`); else all its arguments (a delete, move or rename, plus the receiver for a method). So
  `fs.copyFileSync(process.argv[2], 'o.log')` and `FileUtils.cp(ARGV[0], 'o.log')` read their argument, and
  `fs.copyFileSync('a', process.argv[2])` writes it. A call with no write mode (`open(f)`) is
  a read and has no target; a named mode (`open(f, mode)`) counts as a write, except on a method `.open`.
- A target name is traced back through its bindings, assignments, unpackings, loops and function parameters. A name
  counts as argv when the trace reaches an argv marker (`sys.argv`, `ARGV`, `process.argv`, `$*`, `parse_args`,
  `Deno.args` and similar, searched with string literals blanked), or reaches a name the code never sets. A name
  that has a binding is traced through it even when it is spelled like a language name (`new`, `process`,
  `ENV`), so `old, new = sys.argv[1:3]` makes `new` argv. A name with no binding that the code imports or
  the language supplies (`True`, `None`, `process`, `__dirname`) is not argv, and neither is a capitalized name with
  no binding (`open(OUT, 'w')`), read as a class or module. A call
  result is a fresh value unless the call is a path wrapper (`str`, `Path`, `join`, `abspath` and similar), whose
  arguments are traced. Each name is traced once per script.
- A child process call (`subprocess`, `os.system`, `child_process`, perl or ruby `system` and backticks) counts as a
  write only when its text visibly runs an editor: `sed -i`, `tee`, `cp`, `mv`, `rm`, `install`. So
  `subprocess.Popen(['claude', '-p', plan], stdout=open('l', 'w'))` passes.
- A statement ends at the first close bracket or `;` after the call, and a newline ends an unclosed quote, so an
  apostrophe in a comment no longer joins two statements.

## Evidence

- A bench run's session started a helper script with a tracked plan file as an argument. The script read the plan
  and wrote only a pid file and a log under `.git/`. The gate denied it twice because the plan was tracked and the
  script had some write, the review never ran, and the session asked the user to run it by hand.

## Result

Against the gate before this change, the new pass tests are denied. After it, `test_shell_write_gate.py` passes,
including a copy of the helper script that started the denial, and the denied shapes: unpacking, argparse and parser
libraries, a `main(argv)` parameter, `fileinput` in place, `open(str(out), 'w')`,
`open(os.path.abspath(sys.argv[1]), 'w')`, renames, copies and deletes in python and node, `unlink` and `rename` in
perl, `File` and `FileUtils` calls in ruby, and editors run by a child process. Ruff passes.

Known limits. Fail-open: `open(mode='w', file=argv)`; `os.open` with `O_WRONLY`; `fs.cpSync`; ruby `File.new` and
`File.binwrite`; `from subprocess import run` then a bare `run([...])`; an option such as `--out=tracked.txt` passed to
the script; a target built as `foo() + x + foo()`; a local helper that returns argv (`args = parse_arguments(); open(args.out, 'w')`); a name
bound to `f(argv_name)` where `f` is not a path wrapper; ruby `File.open(f, File::WRONLY)`; a tracked path written
literally in backticks in JS (`fs.writeFileSync(`tracked.txt`, 'y')`), which the string-literal reader does not touch;
`fs.openSync(path, 'w')`; perl `open(my $f, "+<", $ARGV[0])`, since the write-mode test has no `+<`; an editor behind a
wrapper word (`bash -c "rm ..."`, a privilege wrapper), since only the word after the call name counts; a call such as
`os.path.dirname(name)` that is not a path wrapper;
perl `File::Copy` `copy` and `move`, a bare `truncate(` and a bare `rmdir(` in perl, which are not recognized; a name
filled by mutation (`files=[]; files.append(a)`, `c.out = sys.argv[1]` with `c = Config()`); JS
`if (process.argv[2]) out = process.argv[2];` after an earlier `let out='d'`; a receiver on the line above its method
(`(Path(sys.argv[1])\n .write_text('x'))`); `from sys import argv as a`, since an imported alias counts as supplied; an
editor command held in a name (`cmd=['rm', x]; subprocess.run(cmd)`, `os.system(cmd)`); `import subprocess as sp`
then `sp.run`; a bare `rmtree(` or `remove(` from a `from` import; `os.removedirs`; `fileinput.input(inplace=1)`.
Fail-closed: a one-line `try { fs.rmSync('o.tmp') } catch (e) {}`, `try: Path('a').unlink()` and
`for p in x: Path(p).unlink()` deny with a tracked argument, because the statement keyword lands in the receiver text;
`self.x` targets, a plain JS template literal with a path of its own, names set by a callback or
`with ... as`, and a delete such as `os.remove('tracked.txt')`
of a tracked literal, which the earlier gate let pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. Any untracked script with a file write is again denied whenever a tracked file is among its
arguments.
