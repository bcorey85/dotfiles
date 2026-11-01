---
type: "Change"
change_type: "fixed"
title: "shell-write-gate reads a name joined onto a base off the cwd as no write to the cwd file"
description: "A script that writes `tree / 'CLAUDE.md'` with `tree` built under the home folder or a temp dir runs: shell-write-gate no longer reads the joined name as a write to the session repo's own CLAUDE.md. Bench drivers run with no hand-off to the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T20:22:55-05:00"}
seq: 410
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_name_joined_onto_a_base_off_the_cwd_is_not_a_write_to_the_cwd_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

- When a write target, or a text it is bound to, is one value that joins literals onto a base (`B / 'a'`,
  `B + 'a'`, `os.path.join(B, 'a')`, `Path(B, 'a')`), the gate traces the base. When the base cannot be the cwd, the
  joined literals are dropped from the candidates it checks against the cwd.
- A base cannot be the cwd when it is a call that makes a new root (`home`, `gettempdir`, `mkdtemp`,
  `TemporaryDirectory`), a path call on one, or a name whose every binding is one. A call to a function the script
  defines is what that function returns; a name unpacked from its returned tuple (`tree, sha = build()`) is the
  part at its position.
- A base may be the cwd, and the gate denies as before, when it is a string literal, a cwd call (`Path.cwd()`,
  `os.getcwd()`, `Path()`), argv, a name with no binding (`__file__` included), any other call (`os.path.dirname`,
  `subprocess.check_output`, `os.environ.get`, a lambda), a defined function with no return found, or a trace past
  eight steps.

## Evidence

judgment: the gate denied `python3 bin/rule_meter.py run-all --dry-run` twice on one day. The script writes
`tree / "CLAUDE.md"` where `tree` is built from `Path.home() / "dev/evals/..."`, and the gate resolved the bare
`"CLAUDE.md"` against the session cwd, the agent-evals repo.

## Result

The named test fails before (all four shapes denied: a tree under home, a temp dir, an append in a helper, a name
unpacked from a helper's tuple) and passes after. A companion test keeps the shapes that may
write the repo's own CLAUDE.md denied: a bare literal, a cwd call, `os.getcwd()`, `Path()`, `Path('.')`, a
parameter given `Path('.')`, a helper that returns `Path('.')`, argv, an unbound name, and calls off the allow-list
(`os.path.dirname(__file__)`, `subprocess.check_output`, `os.environ.get`, a lambda, a helper with no return). The
rule_meter command is allowed. A base built from `Path(__file__)` or `os.path.dirname(__file__)` stays denied: the
script's own folder may be the repo.

## Watch

None. A wrong deny shows in the session that hits it.

## Back-out

Revert `joined_off_cwd`, `base_may_be_cwd`, `returned_texts`, their constants, and the root-less branch of
`written_candidates`, and the two tests.
