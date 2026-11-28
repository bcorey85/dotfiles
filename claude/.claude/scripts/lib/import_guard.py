"""Makes a fail-closed hook exit 2 when one of its own imports crashes. Standard library only, and it imports nothing
of the toolkit, so a broken sibling module cannot break it.

A hook that crashes before `hook_input.run_gate` starts exits 1, which Claude Code reads as a non-blocking error and
runs the tool call anyway. A gate puts its `lib` folder on sys.path, imports this module, calls `guard` with its module
name, and then imports the rest. `guard` acts only when the gate runs as the hook, so a test that imports the gate as a
library keeps its own excepthook:

    import import_guard
    import_guard.guard("git-discipline-gate", __name__)
    import hook_input

Any exception that then escapes the module's top level (an import error, a syntax error in a sibling) prints one line
on stderr naming the gate and the recovery step, and exits 2. That also covers a crash in the module's own top-level
code. A `SystemExit` is not touched.
"""
import os
import sys

RECOVERY = ("fix the file the error names with the Edit tool (every {tool} call is blocked while a shared gate "
            "module is broken), or ask the user to run `git restore <file>`")

READ_STEP = "before it could read the call"
JUDGING_STEP = "while judging the call"
# A crash after the call was read says nothing about every call of the gate's tool, so it gets no claim about them.
JUDGING_RECOVERY = "fix the file the error names with the Edit tool, or ask the user to run `git restore <file>`"


def crash_line(gate_name, error, before_read=True, tool="Bash"):
    """The stderr line of a gate that crashed, before it read the call (the default) or while it judged it."""
    when = READ_STEP if before_read else JUDGING_STEP
    recovery = RECOVERY.format(tool=tool) if before_read else JUDGING_RECOVERY
    return (f"[{gate_name}] crashed {when} "
            f"({type(error).__name__}: {error}) - exit 2 (a call that has not run yet is blocked). "
            f"Recovery: {recovery}.\n")


def guard(gate_name, module_name="__main__", tool="Bash"):
    """Turn an uncaught exception at the module's top level into exit 2 with a stderr line that names the gate.

    Does nothing unless `module_name` is `__main__`: a gate imported as a library keeps the caller's excepthook.
    Returns a function that puts the default excepthook back, for a gate whose later code is not a hook (a CLI verb
    keeps its traceback)."""
    if module_name != "__main__":
        return lambda: None

    def block_on_crash(_error_type, error, _traceback):
        sys.stderr.write(crash_line(gate_name, error, tool=tool))
        sys.stderr.flush()
        os._exit(2)

    def release():
        sys.excepthook = sys.__excepthook__

    sys.excepthook = block_on_crash
    return release
